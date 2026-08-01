from datetime import datetime

from pydantic import BaseModel, ConfigDict


class AcceptanceCriterionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    text: str
    order: int


class RequirementAnalysisOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    actors: list[str] | None
    preconditions: list[str] | None
    main_flow: list[str] | None
    alt_flows: list[str] | None
    ambiguities: list[str] | None


class PipelineRunOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_story_id: int
    mode: str
    status: str
    current_stage: str | None
    created_at: datetime
    completed_at: datetime | None


class RequirementAnalysisResult(BaseModel):
    run: PipelineRunOut
    analysis: RequirementAnalysisOut | None
    acceptance_criteria: list[AcceptanceCriterionOut]
    error: str | None = None


class TestCaseOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    version: int
    parent_test_case_id: int | None = None
    title: str
    steps: list[str] | None
    expected_result: str | None
    type: str | None
    priority: str | None
    traces_to: int | None
    generated_by: str
    status: str


class TestGenerationResult(BaseModel):
    run: PipelineRunOut
    test_cases: list[TestCaseOut]
    error: str | None = None


class DebateTurnOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    round: int
    speaker: str
    content: dict | None
    created_at: datetime


class DebateResult(BaseModel):
    run: PipelineRunOut
    rounds_used: int
    consensus_reached: bool
    revisions_made: int
    total_findings: int
    turns: list[DebateTurnOut]
    test_cases: list[TestCaseOut]
    error: str | None = None
