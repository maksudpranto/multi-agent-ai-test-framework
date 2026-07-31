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
