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
from app.llm.service import extract_json
from app.models import (
    AcceptanceCriterion,
    AgentExecution,
    ExecutionStatus,
    ExperimentMode,
    PipelineRun,
    PipelineStage,
    Project,
    RequirementAnalysis,
    RunStatus,
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
