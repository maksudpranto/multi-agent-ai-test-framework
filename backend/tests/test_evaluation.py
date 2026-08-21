"""Phase 2 verification: the experiment runner, per-run metrics, and the stats.

Two layers:
  - pure statistics checked against hand-computed values (a Wilcoxon a human can
    verify on paper), so the significance number the thesis reports is trusted;
  - the runner end-to-end on the deterministic mock provider — a full 3-condition
    study over the benchmark completes, persists metrics, is resumable, and
    realises the ablation (no debate turns when the debate is off).

All offline: mock provider, in-memory DB, no API key, no network.
"""
import math

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.benchmark.seed import seed_benchmark
from app.database import Base
from app.evaluation import metrics as M
from app.evaluation.runner import ExperimentRunner
from app.evaluation.stats import (
    aggregate_experiment,
    cohens_dz,
    describe,
    rank_biserial,
    wilcoxon_signed_rank,
)
from app.llm import LLMService
from app.llm.mock_provider import MockProvider
from app.llm.service import _dev_mock_responder
from app.models import (
    DebateTurn,
    Experiment,
    ExperimentMetric,
    ExperimentMode,
    PipelineRun,
    RunStatus,
    User,
)
from app.prompts.seed import seed_prompts
from app.workflow.engine import DefaultWorkflowEngine


# --- Pure statistics (hand-verifiable) --------------------------------------


def test_wilcoxon_all_positive_small_sample():
    """Differences [1, 2, 3]: ranks [1, 2, 3], W+=6, mean=3, var=3.5,
    z=(6-3-0.5)/sqrt(3.5)=1.3363, p=2*(1-Phi(z))~=0.1814. Verifiable by hand."""
    x, y = [11, 12, 13], [10, 10, 10]  # diffs 1, 2, 3
    res = wilcoxon_signed_rank(x, y)
    assert res["statistic"] == 6.0
    assert res["n"] == 3
    assert res["z"] == pytest.approx(1.3363, abs=1e-3)
    assert res["p_value"] == pytest.approx(0.1814, abs=1e-3)


def test_wilcoxon_identical_samples_p_is_one():
    res = wilcoxon_signed_rank([1, 2, 3], [1, 2, 3])
    assert res["n"] == 0
    assert res["p_value"] == 1.0


def test_wilcoxon_larger_clearly_significant():
    """A consistent, sizeable improvement across 10 items is significant."""
    x = [0.9] * 10
    y = [0.4] * 10
    res = wilcoxon_signed_rank(x, y)
    assert res["p_value"] < 0.05


def test_cohens_dz_and_rank_biserial():
    x, y = [11, 12, 13], [10, 10, 10]  # diffs 1, 2, 3: mean 2, stdev 1
    assert cohens_dz(x, y) == pytest.approx(2.0, abs=1e-6)
    assert rank_biserial(x, y) == 1.0  # all improvements
    assert rank_biserial(y, x) == -1.0  # all regressions


def test_describe_basic():
    d = describe([1.0, 2.0, 3.0, 4.0])
    assert d["n"] == 4
    assert d["mean"] == 2.5
    assert d["median"] == 2.5
    assert d["min"] == 1.0 and d["max"] == 4.0
    assert d["std"] == pytest.approx(math.sqrt(5.0 / 3.0), abs=1e-4)


# --- Runner end-to-end on the mock provider ---------------------------------


@pytest.fixture(scope="module")
def experiment():
    """Seed the benchmark and run a full 3-condition study once (mock)."""
    engine_db = create_engine(
        "sqlite:///:memory:", connect_args={"check_same_thread": False}
    )
    Base.metadata.create_all(engine_db)
    db = sessionmaker(bind=engine_db)()
    seed_prompts(db)
    user = User(email="e@e.com", hashed_password="h")
    db.add(user)
    db.commit()
    info = seed_benchmark(db, user.id)
    exp = Experiment(
        owner_id=user.id,
        name="Study",
        dataset_id=info["dataset_id"],
        mode=ExperimentMode.multi_agent,
        conditions=["single_llm", "full_pipeline", "ablation_no_debate"],
    )
    db.add(exp)
    db.commit()

    engine = DefaultWorkflowEngine(
        LLMService(MockProvider(responder=_dev_mock_responder))
    )
    runner = ExperimentRunner(engine, model="mock")
    summary = runner.run_experiment(db, exp.id)
    yield {"db": db, "exp_id": exp.id, "summary": summary, "runner": runner, "n_items": info["n_items"]}
    db.close()


def test_runner_completes_full_grid(experiment):
    s = experiment["summary"]
    assert s["total_cells"] == experiment["n_items"] * 3
    assert s["completed"] == s["total_cells"]
    assert s["failed"] == 0


def test_every_run_is_completed_and_scored(experiment):
    db = experiment["db"]
    runs = list(
        db.scalars(
            select(PipelineRun).where(PipelineRun.experiment_id == experiment["exp_id"])
        )
    )
    assert len(runs) == experiment["n_items"] * 3
    assert all(r.status == RunStatus.completed for r in runs)
    # Every run has a persisted mutation-score metric.
    for r in runs:
        ms = db.scalar(
            select(ExperimentMetric.metric_value).where(
                ExperimentMetric.pipeline_run_id == r.id,
                ExperimentMetric.metric_name == M.MUTATION_SCORE,
            )
        )
        assert ms is not None


def test_experiment_marked_completed(experiment):
    db = experiment["db"]
    exp = db.get(Experiment, experiment["exp_id"])
    assert exp.status == RunStatus.completed
    assert exp.completed_at is not None


def test_resumable_second_run_skips_all(experiment):
    """Re-running the same experiment does no new work — every cell is skipped."""
    db = experiment["db"]
    resumed = experiment["runner"].run_experiment(db, experiment["exp_id"])
    assert resumed["skipped"] == resumed["total_cells"]
    assert resumed["completed"] == 0
    # And no duplicate runs were created.
    n_runs = db.scalar(
        select(ExperimentMetric.pipeline_run_id)
    ) is not None
    runs = list(
        db.scalars(
            select(PipelineRun).where(PipelineRun.experiment_id == experiment["exp_id"])
        )
    )
    assert len(runs) == experiment["n_items"] * 3


def test_ablation_no_debate_has_no_debate_turns(experiment):
    """The ablation must actually skip the debate; the full pipeline must run
    it. This is what makes 'no debate' a real, measured arm."""
    db = experiment["db"]

    def debate_turns_for(condition: str) -> int:
        run_ids = [
            r.id
            for r in db.scalars(
                select(PipelineRun).where(
                    PipelineRun.experiment_id == experiment["exp_id"],
                    PipelineRun.experiment_condition == condition,
                )
            )
        ]
        return db.scalar(
            select(DebateTurn)
            .where(DebateTurn.pipeline_run_id.in_(run_ids))
            .limit(1)
        ) is not None

    assert debate_turns_for("ablation_no_debate") is False
    assert debate_turns_for("full_pipeline") is True


def test_repetitions_run_full_grid_and_report_spread():
    """A 2-repetition study runs the grid twice and reports a run-to-run spread.
    On the deterministic mock every repetition is identical, so the spread is 0."""
    engine_db = create_engine(
        "sqlite:///:memory:", connect_args={"check_same_thread": False}
    )
    Base.metadata.create_all(engine_db)
    db = sessionmaker(bind=engine_db)()
    seed_prompts(db)
    user = User(email="rep@e.com", hashed_password="h")
    db.add(user)
    db.commit()
    info = seed_benchmark(db, user.id)
    exp = Experiment(
        owner_id=user.id, name="Rep", dataset_id=info["dataset_id"],
        mode=ExperimentMode.multi_agent,
        conditions=["single_llm", "full_pipeline"], repetitions=2,
    )
    db.add(exp)
    db.commit()

    engine = DefaultWorkflowEngine(
        LLMService(MockProvider(responder=_dev_mock_responder))
    )
    summary = ExperimentRunner(engine, model="mock").run_experiment(db, exp.id)
    assert summary["total_cells"] == info["n_items"] * 2 * 2  # items x conds x reps
    assert summary["completed"] == summary["total_cells"]

    agg = aggregate_experiment(db, exp.id)
    assert agg["n_reps"] == 2
    for c in agg["conditions"]:
        assert c["n_reps"] == 2
        assert c["run_to_run_std"] == 0.0  # deterministic mock => no spread
    db.close()


def test_aggregate_shape_and_pairwise(experiment):
    db = experiment["db"]
    agg = aggregate_experiment(db, experiment["exp_id"])
    assert agg["n_items"] == experiment["n_items"]
    assert {c["key"] for c in agg["conditions"]} == {
        "single_llm", "full_pipeline", "ablation_no_debate"
    }
    # One comparison per non-baseline condition, each paired across all items.
    assert len(agg["comparisons"]) == 2
    for cmp in agg["comparisons"]:
        assert cmp["baseline"] == "single_llm"
        assert cmp["n_pairs"] == experiment["n_items"]
        assert "p_value" in cmp and 0.0 <= cmp["p_value"] <= 1.0
    assert agg["headline"]["available"] is True
