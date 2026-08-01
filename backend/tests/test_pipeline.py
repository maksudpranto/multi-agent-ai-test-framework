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
    PipelineRun,
    PipelineStage,
    Project,
    RequirementAnalysis,
    RunStatus,
    TestCase as GeneratedTestCase,
    User,
    UserStory,
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
    story = UserStory(
        project_id=project.id, title="Login", raw_text="As a user I want to log in"
    )
    db.add(story)
    db.commit()
    return story


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
        user_story_id=story.id,
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
        user_story_id=story.id,
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
        user_story_id=story.id,
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
        user_story_id=story.id,
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
    assert len(before) == 3  # one per acceptance criterion (AC1..AC3)

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


def test_single_llm_baseline_runs_untraceable(db):
    seed_prompts(db)
    story = _seed_story(db)
    llm = LLMService(MockProvider(responder=_dev_mock_responder))
    engine = DefaultWorkflowEngine(llm_service=llm)

    run = PipelineRun(
        user_story_id=story.id,
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
