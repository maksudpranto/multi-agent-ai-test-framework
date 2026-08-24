"""Phase 3 verification: the evaluation API end-to-end via FastAPI TestClient.

Exercises the real HTTP surface — seed the benchmark, list conditions + items,
create an experiment, run it (the background task completes within the test
client), poll status to completed, then read aggregated results and an item
drill-down. Runs on an isolated in-memory DB with the mock provider: both the
request session (via the get_db override) and the background runner session (via
a patched SessionLocal) point at the same in-memory engine, so the study is fully
self-contained.
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.evaluation.runner as runner_mod
from app.auth.security import create_access_token
from app.database import Base, get_db
from app.llm import LLMService
from app.llm.mock_provider import MockProvider
from app.llm.service import _dev_mock_responder
from app.main import app
from app.models import User
from app.prompts.seed import seed_prompts
from app.workflow.engine import DefaultWorkflowEngine


@pytest.fixture
def client(monkeypatch):
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,  # one shared connection => one in-memory DB
    )
    Base.metadata.create_all(engine)
    TestingSessionLocal = sessionmaker(bind=engine)

    # Seed prompts + a user directly.
    setup = TestingSessionLocal()
    seed_prompts(setup)
    user = User(email="api@e.com", hashed_password="h")
    setup.add(user)
    setup.commit()
    user_id = user.id
    setup.close()

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    # The background runner opens its own session; point it at the same engine.
    monkeypatch.setattr(runner_mod, "SessionLocal", TestingSessionLocal)

    # Force the deterministic mock engine regardless of the dev .env provider,
    # so the study is offline, free, and reproducible.
    def _mock_engine(provider, model):
        engine = DefaultWorkflowEngine(
            LLMService(MockProvider(responder=_dev_mock_responder))
        )
        return engine, "mock"

    monkeypatch.setattr(runner_mod, "_resolve_engine_and_model", _mock_engine)

    token = create_access_token(str(user_id))
    test_client = TestClient(app)
    test_client.headers.update({"Authorization": f"Bearer {token}"})
    yield test_client
    app.dependency_overrides.clear()


def test_full_evaluation_flow(client):
    # Conditions catalog.
    r = client.get("/evaluation/conditions")
    assert r.status_code == 200
    keys = {c["key"] for c in r.json()}
    assert {"single_llm", "full_pipeline", "ablation_no_debate"} <= keys

    # Seed the benchmark.
    r = client.post("/evaluation/benchmark/seed")
    assert r.status_code == 200
    seed = r.json()
    assert seed["n_items"] == 16
    dataset_id = seed["dataset_id"]

    # List items.
    r = client.get(f"/evaluation/datasets/{dataset_id}/items")
    assert r.status_code == 200
    items = r.json()
    assert len(items) == 16
    assert all(it["n_mutants"] == 4 for it in items)
    a_requirement = items[0]["requirement_id"]

    # Create an experiment.
    r = client.post(
        "/evaluation/experiments",
        json={"name": "API study", "conditions": ["single_llm", "full_pipeline"]},
    )
    assert r.status_code == 201
    exp = r.json()
    assert exp["status"] == "pending"
    assert exp["conditions"] == ["single_llm", "full_pipeline"]
    exp_id = exp["id"]

    # Run it (background task completes within the TestClient call).
    r = client.post(f"/evaluation/experiments/{exp_id}/run", json={})
    assert r.status_code == 202

    # Status -> completed, full progress.
    r = client.get(f"/evaluation/experiments/{exp_id}")
    assert r.status_code == 200
    stat = r.json()
    assert stat["experiment"]["status"] == "completed"
    assert stat["progress"]["completed"] == stat["progress"]["total"] == 32  # 16 items x 2

    # Results with pairwise significance.
    r = client.get(f"/evaluation/experiments/{exp_id}/results")
    assert r.status_code == 200
    results = r.json()
    assert results["n_items"] == 16
    assert {c["key"] for c in results["conditions"]} == {"single_llm", "full_pipeline"}
    assert len(results["comparisons"]) == 1
    comp = results["comparisons"][0]
    assert comp["condition"] == "full_pipeline"
    assert comp["n_pairs"] == 16
    assert 0.0 <= comp["p_value"] <= 1.0
    assert results["headline"]["available"] is True

    # Fault-type breakdown: the taxonomy legend plus per-condition kill counts.
    ft = results["fault_types"]
    assert {f["key"] for f in ft["legend"]} == {
        "boundary", "wrong_constant", "wrong_operator", "missing_condition", "control_flow",
    }
    for cond_key in ("single_llm", "full_pipeline"):
        rows = ft["by_condition"][cond_key]
        assert rows, f"no fault-type rows for {cond_key}"
        for cls in rows.values():
            assert 0 <= cls["killed"] <= cls["total"]

    # Cost-effectiveness metric is reported per condition.
    for c in results["conditions"]:
        assert "faults_per_1k_tokens" in c["metrics"]

    # Drill-down for one item.
    r = client.get(f"/evaluation/experiments/{exp_id}/items/{a_requirement}")
    assert r.status_code == 200
    drill = r.json()
    assert drill["item"] is not None
    assert {c["condition"] for c in drill["conditions"]} == {"single_llm", "full_pipeline"}
    for cond in drill["conditions"]:
        assert "mutation_score" in cond["metrics"]
    # Every seeded bug carries its fault class for the per-bug view.
    assert all(m["fault_type"] for m in drill["item"]["mutants"])


def test_rename_and_delete_experiment(client):
    client.post("/evaluation/benchmark/seed")
    exp_id = client.post("/evaluation/experiments", json={"name": "Original"}).json()["id"]

    # Rename.
    r = client.patch(f"/evaluation/experiments/{exp_id}", json={"name": "Renamed study"})
    assert r.status_code == 200
    assert r.json()["name"] == "Renamed study"
    assert client.get(f"/evaluation/experiments/{exp_id}").json()["experiment"]["name"] == "Renamed study"

    # Empty name rejected.
    assert client.patch(f"/evaluation/experiments/{exp_id}", json={"name": "  "}).status_code == 422

    # A pending experiment can be cancelled; a second stop is then a 409.
    assert client.post(f"/evaluation/experiments/{exp_id}/stop").status_code == 200
    assert client.get(f"/evaluation/experiments/{exp_id}").json()["experiment"]["status"] == "cancelled"
    assert client.post(f"/evaluation/experiments/{exp_id}/stop").status_code == 409

    # Delete, then it's gone.
    assert client.delete(f"/evaluation/experiments/{exp_id}").status_code == 204
    assert client.get(f"/evaluation/experiments/{exp_id}").status_code == 404


def test_quick_scope_runs_only_the_subset(client):
    """A 'quick' experiment covers only the representative subset — far fewer
    cells than a full run — so iterating stays cheap."""
    from app.benchmark.corpus import QUICK_SLUGS

    client.post("/evaluation/benchmark/seed")
    exp = client.post(
        "/evaluation/experiments",
        json={"name": "Quick", "conditions": ["single_llm", "full_pipeline"], "scope": "quick"},
    ).json()
    assert exp["scope"] == "quick"

    assert client.post(f"/evaluation/experiments/{exp['id']}/run", json={}).status_code == 202

    stat = client.get(f"/evaluation/experiments/{exp['id']}").json()
    # subset programs x 2 conditions x 1 repeat
    assert stat["progress"]["total"] == len(QUICK_SLUGS) * 2

    res = client.get(f"/evaluation/experiments/{exp['id']}/results").json()
    assert res["n_items"] == len(QUICK_SLUGS)
    assert len(res["ran_requirement_ids"]) == len(QUICK_SLUGS)


def test_delete_removes_runs_and_metrics(client):
    """Deleting an experiment removes its runs and metrics too."""
    from sqlalchemy import select
    import app.evaluation.runner as rm
    from app.models import ExperimentMetric, PipelineRun

    client.post("/evaluation/benchmark/seed")
    exp_id = client.post(
        "/evaluation/experiments",
        json={"name": "ToDelete", "conditions": ["single_llm"]},
    ).json()["id"]
    client.post(f"/evaluation/experiments/{exp_id}/run", json={})
    # Runs + metrics now exist.
    db = rm.SessionLocal()
    assert db.scalar(select(PipelineRun).where(PipelineRun.experiment_id == exp_id)) is not None
    db.close()

    assert client.delete(f"/evaluation/experiments/{exp_id}").status_code == 204

    db = rm.SessionLocal()
    assert db.scalar(select(PipelineRun).where(PipelineRun.experiment_id == exp_id)) is None
    assert db.scalar(select(ExperimentMetric).where(ExperimentMetric.experiment_id == exp_id)) is None
    db.close()


def test_results_requires_ownership(client):
    # A different user's token cannot read the experiment.
    r = client.post("/evaluation/benchmark/seed")
    assert r.status_code == 200
    r = client.post("/evaluation/experiments", json={"name": "Owned"})
    exp_id = r.json()["id"]

    other = create_access_token("999999")
    r = client.get(
        f"/evaluation/experiments/{exp_id}",
        headers={"Authorization": f"Bearer {other}"},
    )
    assert r.status_code in (401, 404)
