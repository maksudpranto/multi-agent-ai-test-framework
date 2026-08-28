"""Phase 1 verification: the requirement-analysis stage runs end to end through
the engine with a mock LLM (no API key), persists artifacts, and logs an audit
row. Also covers auth/password and JSON extraction."""
import json

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.agents.requirement_analysis import RequirementAnalysisAgent  # noqa: F401
from app.auth.security import hash_password, verify_password
from app.database import Base
from app.llm import LLMService
from app.llm.mock_provider import MockProvider
from app.llm.service import _dev_mock_responder, extract_json
from app.models import (
    AcceptanceCriterion,
    AgentExecution,
    DebateSpeaker,
    DebateTurn,
    ExecutionStatus,
    ExperimentMode,
    GeneratedBy,
    Module,
    PipelineRun,
    PipelineStage,
    Project,
    Requirement,
    RequirementAnalysis,
    RunStatus,
    TestCase as GeneratedTestCase,
    User,
)
from app.prompts.seed import seed_prompts
from app.workflow.config import RunConfig
from app.workflow.engine import DefaultWorkflowEngine

ANALYSIS_JSON = {
    "actors": ["Registered User"],
    "preconditions": ["User has an account"],
    "main_flow": ["Open login", "Enter email + password", "Submit"],
    "alt_flows": ["Wrong password shows error"],
    "acceptance_criteria": [
        {"id": "AC1", "text": "Valid credentials grant access to the dashboard"},
        {"id": "AC2", "text": "Invalid credentials show an error and deny access"},
    ],
    "ambiguities": ["Lockout after N failed attempts not specified"],
}

TEST_CASES_JSON = {
    "test_cases": [
        {
            "acceptance_criterion_id": 1,
            "title": "Grant dashboard access with valid credentials",
            "steps": [
                "Open the login screen",
                "Enter a registered email and valid password",
                "Submit the login form",
            ],
            "expected_result": "The dashboard is displayed to the authenticated user.",
            "type": "functional",
            "priority": "high",
        }
    ]
}


@pytest.fixture
def db():
    engine = create_engine(
        "sqlite:///:memory:", connect_args={"check_same_thread": False}
    )
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close()


def _seed_story(db):
    user = User(email="t@e.com", hashed_password=hash_password("secret123"))
    db.add(user)
    db.flush()
    project = Project(owner_id=user.id, name="Demo")
    db.add(project)
    db.flush()
    module = Module(project_id=project.id, name="Auth")
    db.add(module)
    db.flush()
    requirement = Requirement(
        project_id=project.id,
        module_id=module.id,
        title="Login",
        raw_text="As a user I want to log in",
    )
    db.add(requirement)
    db.commit()
    return requirement


def test_password_roundtrip():
    h = hash_password("secret123")
    assert verify_password("secret123", h)
    assert not verify_password("wrong", h)


def test_extract_json_variants():
    assert extract_json('{"a": 1}') == {"a": 1}
    assert extract_json('```json\n{"a": 1}\n```') == {"a": 1}
    assert extract_json('here is the result: {"a": 1} done') == {"a": 1}


def test_requirement_analysis_stage_persists_and_logs(db):
    seed_prompts(db)
    story = _seed_story(db)

    run = PipelineRun(
        requirement_id=story.id,
        mode=ExperimentMode.multi_agent,
        current_stage=PipelineStage.requirement_analysis,
        status=RunStatus.running,
    )
    db.add(run)
    db.commit()
    db.refresh(run)

    llm = LLMService(MockProvider(response=json.dumps(ANALYSIS_JSON)))
    engine = DefaultWorkflowEngine(llm_service=llm)
    result = engine.run_stage(
        db,
        run,
        PipelineStage.requirement_analysis,
        inputs={"user_story": story.raw_text},
        config=RunConfig(model="mock-model"),
    )

    assert result.success
    assert result.output["acceptance_criteria"][0]["id"] == "AC1"

    analysis = db.scalar(
        select(RequirementAnalysis).where(
            RequirementAnalysis.pipeline_run_id == run.id
        )
    )
    assert analysis is not None
    assert analysis.actors == ["Registered User"]

    criteria = list(
        db.scalars(
            select(AcceptanceCriterion).where(
                AcceptanceCriterion.pipeline_run_id == run.id
            )
        )
    )
    assert len(criteria) == 2

    execution = db.scalar(
        select(AgentExecution).where(AgentExecution.pipeline_run_id == run.id)
    )
    assert execution is not None
    assert execution.status == ExecutionStatus.success
    assert execution.prompt_version == "v1"
    assert execution.tokens_in and execution.tokens_out


def test_requirement_analysis_stage_handles_bad_json(db):
    seed_prompts(db)
    story = _seed_story(db)
    run = PipelineRun(
        requirement_id=story.id,
        mode=ExperimentMode.multi_agent,
        status=RunStatus.running,
    )
    db.add(run)
    db.commit()
    db.refresh(run)

    llm = LLMService(MockProvider(response="totally not json"))
    engine = DefaultWorkflowEngine(llm_service=llm)
    result = engine.run_stage(
        db,
        run,
        PipelineStage.requirement_analysis,
        inputs={"user_story": story.raw_text},
        config=RunConfig(model="mock-model"),
    )

    assert not result.success
    assert result.error
    execution = db.scalar(
        select(AgentExecution).where(AgentExecution.pipeline_run_id == run.id)
    )
    assert execution.status == ExecutionStatus.failed
    # No artifacts persisted on failure.
    assert db.scalar(
        select(RequirementAnalysis).where(
            RequirementAnalysis.pipeline_run_id == run.id
        )
    ) is None


def test_test_generation_stage_persists_traceable_test_cases(db):
    seed_prompts(db)
    story = _seed_story(db)
    run = PipelineRun(
        requirement_id=story.id,
        mode=ExperimentMode.multi_agent,
        current_stage=PipelineStage.test_generation,
        status=RunStatus.running,
    )
    db.add(run)
    db.flush()
    criterion = AcceptanceCriterion(
        pipeline_run_id=run.id,
        text="Valid credentials grant access to the dashboard",
        order=0,
    )
    db.add(criterion)
    db.commit()

    response = TEST_CASES_JSON.copy()
    response["test_cases"] = [dict(TEST_CASES_JSON["test_cases"][0])]
    response["test_cases"][0]["acceptance_criterion_id"] = criterion.id
    llm = LLMService(MockProvider(response=json.dumps(response)))
    engine = DefaultWorkflowEngine(llm_service=llm)
    result = engine.run_stage(
        db,
        run,
        PipelineStage.test_generation,
        inputs={
            "user_story": story.raw_text,
            "acceptance_criteria": [{"id": criterion.id, "text": criterion.text}],
        },
        config=RunConfig(model="mock-model"),
    )

    assert result.success
    test_case = db.scalar(
        select(GeneratedTestCase).where(GeneratedTestCase.pipeline_run_id == run.id)
    )
    assert test_case is not None
    assert test_case.traces_to == criterion.id
    assert test_case.version == 1
    assert test_case.steps[0] == "Open the login screen"


# --- Phase 3+4: multi-agent Reviewer <-> Consensus debate, offline via mock ---


def _run_multi_agent_through_generation(db):
    """Drive requirement analysis + test generation with the offline mock
    responder, returning the engine/run/story/criteria/config to debate over."""
    seed_prompts(db)
    story = _seed_story(db)
    llm = LLMService(MockProvider(responder=_dev_mock_responder))
    engine = DefaultWorkflowEngine(llm_service=llm)
    cfg = RunConfig(model="mock-model")

    run = PipelineRun(
        requirement_id=story.id,
        mode=ExperimentMode.multi_agent,
        status=RunStatus.running,
    )
    db.add(run)
    db.commit()
    db.refresh(run)

    engine.run_stage(
        db, run, PipelineStage.requirement_analysis,
        inputs={"user_story": story.raw_text}, config=cfg,
    )
    criteria = list(
        db.scalars(
            select(AcceptanceCriterion)
            .where(AcceptanceCriterion.pipeline_run_id == run.id)
            .order_by(AcceptanceCriterion.order)
        )
    )
    engine.run_stage(
        db, run, PipelineStage.test_generation,
        inputs={
            "user_story": story.raw_text,
            "acceptance_criteria": [{"id": c.id, "text": c.text} for c in criteria],
        },
        config=cfg,
    )
    return engine, run, story, criteria, cfg


def test_debate_reaches_consensus_and_versions_test_cases(db):
    engine, run, story, criteria, cfg = _run_multi_agent_through_generation(db)

    before = list(
        db.scalars(
            select(GeneratedTestCase).where(GeneratedTestCase.pipeline_run_id == run.id)
        )
    )
    # The generator now produces a full suite (multiple typed cases per
    # criterion), not one case each. Every criterion must be covered, and the
    # suite must span more than just the happy path.
    assert len(before) >= 3
    assert {c.traces_to for c in before} == {c.id for c in criteria}
    assert {c.type for c in before} >= {"functional", "negative"}
    assert any(c.test_data for c in before)

    summary = engine.run_debate(
        db, run,
        user_story=story.raw_text,
        acceptance_criteria=[{"id": c.id, "text": c.text} for c in criteria],
        config=cfg,
    )

    # Reviewer flags on round 1, consensus revises, reviewer is satisfied on
    # round 2 -> the loop TERMINATES by consensus, not by exhausting max rounds.
    assert summary["consensus_reached"] is True
    assert summary["rounds_used"] == 2
    assert summary["revisions_made"] >= 1
    assert summary["total_findings"] >= 1

    # Consensus produced a genuine new version (bidirectional revision).
    consensus_versions = list(
        db.scalars(
            select(GeneratedTestCase).where(
                GeneratedTestCase.pipeline_run_id == run.id,
                GeneratedTestCase.generated_by == GeneratedBy.consensus,
            )
        )
    )
    assert consensus_versions
    assert any(v.version == 2 and v.parent_test_case_id for v in consensus_versions)

    # The debate transcript is fully auditable: reviewer(r1), consensus(r1),
    # reviewer(r2).
    turns = list(
        db.scalars(
            select(DebateTurn)
            .where(DebateTurn.pipeline_run_id == run.id)
            .order_by(DebateTurn.id)
        )
    )
    speakers = {(t.round, t.speaker) for t in turns}
    assert (1, DebateSpeaker.reviewer) in speakers
    assert (1, DebateSpeaker.consensus) in speakers
    assert (2, DebateSpeaker.reviewer) in speakers


def test_debate_records_reviewer_findings_in_transcript(db):
    engine, run, story, criteria, cfg = _run_multi_agent_through_generation(db)
    engine.run_debate(
        db, run,
        user_story=story.raw_text,
        acceptance_criteria=[{"id": c.id, "text": c.text} for c in criteria],
        config=cfg,
    )
    first = db.scalar(
        select(DebateTurn)
        .where(
            DebateTurn.pipeline_run_id == run.id,
            DebateTurn.speaker == DebateSpeaker.reviewer,
            DebateTurn.round == 1,
        )
    )
    assert first.content["needs_revision"] is True
    assert first.content["findings"]
    assert first.content["findings"][0]["severity"] in {"high", "medium", "low"}


def test_execution_grounded_debate_uses_reference_and_grounded_prompt(db):
    """The grounded arm builds a ground-truth behaviour table from the reference
    and runs the reviewer with the execution-grounded prompt (never a mutant)."""
    from app.evaluation.harness import reference_behavior_table

    engine, run, story, criteria, cfg = _run_multi_agent_through_generation(db)

    oracle = {
        "reference_code": "def is_even(n):\n    return n % 2 == 0\n",
        "entrypoint": "is_even",
        "canonical_inputs": [[2], [3], [0]],
    }
    evidence = reference_behavior_table(
        oracle["reference_code"], oracle["entrypoint"], oracle["canonical_inputs"]
    )
    assert "is_even(2) -> True" in evidence
    assert "is_even(3) -> False" in evidence

    gcfg = RunConfig(model="mock-model", execution_grounded=True)
    summary = engine.run_debate(
        db, run, user_story=story.raw_text,
        acceptance_criteria=[{"id": c.id, "text": c.text} for c in criteria],
        config=gcfg, oracle=oracle,
    )
    assert summary["rounds_used"] >= 1

    reviewer_execs = db.scalars(
        select(AgentExecution).where(
            AgentExecution.pipeline_run_id == run.id,
            AgentExecution.stage == PipelineStage.reviewer,
        )
    ).all()
    assert reviewer_execs
    assert all(e.prompt_version == "grounded_v1" for e in reviewer_execs)


def test_test_data_agent_fills_sample_data_for_one_case(db):
    """The on-demand Test Data agent produces concrete sample data for a single
    case, logs an audit row, and its output can be persisted onto the case."""
    engine, run, story, criteria, cfg = _run_multi_agent_through_generation(db)

    case = db.scalars(
        select(GeneratedTestCase).where(
            GeneratedTestCase.pipeline_run_id == run.id
        )
    ).first()
    assert case is not None

    result = engine.run_test_data(
        db, run, test_case=case, user_story=story.raw_text, config=cfg
    )
    assert result.success
    assert "test_data" in result.output and result.output["test_data"]

    # The route persists the agent's output onto the case; do the same here.
    case.test_data = result.output["test_data"]
    db.commit()
    db.refresh(case)
    assert case.test_data == result.output["test_data"]

    execution = db.scalar(
        select(AgentExecution).where(
            AgentExecution.pipeline_run_id == run.id,
            AgentExecution.stage == PipelineStage.test_data,
        )
    )
    assert execution is not None and execution.status == ExecutionStatus.success


def test_prioritizer_assigns_rank_and_severity(db):
    engine, run, story, criteria, cfg = _run_multi_agent_through_generation(db)

    result = engine.run_prioritization(
        db, run, user_story=story.raw_text, config=cfg
    )
    assert result.success

    cases = list(
        db.scalars(
            select(GeneratedTestCase).where(
                GeneratedTestCase.pipeline_run_id == run.id
            )
        )
    )
    ranked = [c for c in cases if c.rank is not None]
    # Every current case is ranked, with a severity and a unique rank.
    assert ranked
    assert all(c.severity in {"critical", "major", "minor"} for c in ranked)
    ranks = [c.rank for c in ranked]
    assert len(ranks) == len(set(ranks))  # unique
    assert min(ranks) == 1

    execution = db.scalar(
        select(AgentExecution).where(
            AgentExecution.pipeline_run_id == run.id,
            AgentExecution.stage == PipelineStage.prioritization,
        )
    )
    assert execution is not None and execution.status == ExecutionStatus.success


def test_coverage_reports_traceability_and_gaps(db):
    engine, run, story, criteria, cfg = _run_multi_agent_through_generation(db)

    summary = engine.run_coverage(
        db, run, user_story=story.raw_text, config=cfg
    )
    # Every criterion is covered (the generator makes cases for each), so 100%.
    assert summary["total"] == len(criteria)
    assert summary["covered_count"] == len(criteria)
    assert summary["coverage_pct"] == 100.0

    from app.models import CoverageReport

    reports = list(
        db.scalars(
            select(CoverageReport).where(CoverageReport.pipeline_run_id == run.id)
        )
    )
    assert len(reports) == len(criteria)
    assert all(r.covered and r.covering_test_case_ids for r in reports)

    # An uncovered criterion is reported as a gap.
    orphan = AcceptanceCriterion(
        pipeline_run_id=run.id, text="An untested extra criterion", order=99
    )
    db.add(orphan)
    db.commit()
    summary2 = engine.run_coverage(
        db, run, user_story=story.raw_text, config=cfg
    )
    assert summary2["covered_count"] == len(criteria)  # orphan not covered
    assert summary2["coverage_pct"] < 100.0
    gap = db.scalar(
        select(CoverageReport).where(
            CoverageReport.pipeline_run_id == run.id,
            CoverageReport.acceptance_criterion_id == orphan.id,
        )
    )
    assert gap is not None and gap.covered is False


def test_quality_scores_and_reports(db):
    engine, run, story, criteria, cfg = _run_multi_agent_through_generation(db)

    summary = engine.run_quality(db, run, user_story=story.raw_text, config=cfg)
    assert summary["total"] >= 3
    assert 0.0 <= summary["overall_score"] <= 1.0

    from app.models import QualityReport

    reports = list(
        db.scalars(
            select(QualityReport).where(QualityReport.pipeline_run_id == run.id)
        )
    )
    assert len(reports) == summary["total"]
    for r in reports:
        for s in (r.clarity_score, r.atomicity_score, r.traceability_score):
            assert 0.0 <= s <= 1.0

    execution = db.scalar(
        select(AgentExecution).where(
            AgentExecution.pipeline_run_id == run.id,
            AgentExecution.stage == PipelineStage.quality,
        )
    )
    assert execution is not None and execution.status == ExecutionStatus.success


def test_quality_detects_duplicate_titles(db):
    engine, run, story, criteria, cfg = _run_multi_agent_through_generation(db)
    # Force a deterministic duplicate: add a case with a title identical to an
    # existing current case.
    existing = db.scalar(
        select(GeneratedTestCase).where(GeneratedTestCase.pipeline_run_id == run.id)
    )
    dup = GeneratedTestCase(
        pipeline_run_id=run.id,
        version=1,
        title=existing.title,
        steps=["x"],
        expected_result="y",
        traces_to=existing.traces_to,
    )
    db.add(dup)
    db.commit()

    summary = engine.run_quality(db, run, user_story=story.raw_text, config=cfg)
    assert summary["duplicate_count"] >= 1


def test_single_llm_baseline_runs_untraceable(db):
    seed_prompts(db)
    story = _seed_story(db)
    llm = LLMService(MockProvider(responder=_dev_mock_responder))
    engine = DefaultWorkflowEngine(llm_service=llm)

    run = PipelineRun(
        requirement_id=story.id,
        mode=ExperimentMode.single_llm,
        status=RunStatus.running,
    )
    db.add(run)
    db.commit()
    db.refresh(run)

    result = engine.run_baseline(
        db, run, user_story=story.raw_text, config=RunConfig(model="mock-model")
    )
    assert result.success

    cases = list(
        db.scalars(
            select(GeneratedTestCase).where(GeneratedTestCase.pipeline_run_id == run.id)
        )
    )
    assert len(cases) == 2
    # The baseline has no requirement-analysis stage, so no traceability.
    assert all(c.traces_to is None for c in cases)
