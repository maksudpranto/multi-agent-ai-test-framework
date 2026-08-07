from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ModelSelection(BaseModel):
    """Optional per-run model override the client sends in the request body of
    any pipeline action. When omitted (or partial) the configured default is
    used. Validated against the free-model catalog in the route."""

    provider: str | None = None
    model: str | None = None


class AcceptanceCriteriaIn(ModelSelection):
    """User-supplied acceptance criteria — the alternative input to a full user
    story. Lets a user generate test cases directly from AC, skipping analysis.
    Inherits the optional model selection so this action can pick a model too."""

    criteria: list[str] = Field(min_length=1)


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
    requirement_id: int
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
    test_data: dict | list | None = None
    type: str | None
    priority: str | None
    severity: str | None = None
    rank: int | None = None
    traces_to: int | None
    generated_by: str
    status: str


class TestGenerationResult(BaseModel):
    run: PipelineRunOut
    test_cases: list[TestCaseOut]
    error: str | None = None


class CoverageItemOut(BaseModel):
    acceptance_criterion_id: int
    criterion_text: str
    covered: bool
    covering_test_case_ids: list[int]
    gap_notes: str | None = None


class CoverageResult(BaseModel):
    run: PipelineRunOut
    items: list[CoverageItemOut]
    total: int
    covered_count: int
    coverage_pct: float
    error: str | None = None


class QualityItemOut(BaseModel):
    test_case_id: int
    title: str
    clarity_score: float | None
    atomicity_score: float | None
    traceability_score: float | None
    duplicate_flag: bool
    notes: str | None = None


class QualityResult(BaseModel):
    run: PipelineRunOut
    items: list[QualityItemOut]
    total: int
    overall_score: float
    duplicate_count: int
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
