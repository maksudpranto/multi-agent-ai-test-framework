"""Pydantic contracts for agent structured outputs. Validation happens against
these so a malformed LLM reply is caught (and can be retried/logged) rather
than silently persisted."""
from __future__ import annotations

from pydantic import BaseModel, Field


class AcceptanceCriterionOut(BaseModel):
    id: str = Field(description="Stable short id within this analysis, e.g. AC1")
    text: str


class RequirementAnalysisOut(BaseModel):
    actors: list[str] = Field(default_factory=list)
    preconditions: list[str] = Field(default_factory=list)
    main_flow: list[str] = Field(default_factory=list)
    alt_flows: list[str] = Field(default_factory=list)
    acceptance_criteria: list[AcceptanceCriterionOut] = Field(default_factory=list)
    ambiguities: list[str] = Field(default_factory=list)


class GeneratedTestCaseOut(BaseModel):
    acceptance_criterion_id: int
    title: str = Field(min_length=1)
    steps: list[str] = Field(min_length=1)
    expected_result: str = Field(min_length=1)
    type: str = Field(default="functional")
    priority: str = Field(default="medium")


class TestGenerationOut(BaseModel):
    test_cases: list[GeneratedTestCaseOut] = Field(default_factory=list)
