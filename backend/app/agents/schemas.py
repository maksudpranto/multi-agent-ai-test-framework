"""Pydantic contracts for agent structured outputs. Validation happens against
these so a malformed LLM reply is caught (and can be retried/logged) rather
than silently persisted."""
from __future__ import annotations

from typing import Any

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
    type: str = Field(
        default="functional",
        description="functional | negative | boundary | security | api",
    )
    priority: str = Field(default="medium", description="high | medium | low")
    test_data: dict[str, Any] | list[Any] | None = Field(
        default=None,
        description="Concrete mock data to execute the case, e.g. "
        '{"valid": {...}, "invalid": {...}, "boundary": [...]}',
    )


class TestGenerationOut(BaseModel):
    test_cases: list[GeneratedTestCaseOut] = Field(default_factory=list)


# --- Reviewer -------------------------------------------------------------
# The Reviewer critiques the *current* test cases and, crucially, emits a
# verdict (`needs_revision`) that the engine uses to decide whether the debate
# continues. That verdict is the agent's autonomy — the engine does not decide.


class ReviewFindingOut(BaseModel):
    test_case_id: int | None = Field(
        default=None, description="Test case the issue is about; null for a missing scenario"
    )
    acceptance_criterion_id: int | None = Field(
        default=None, description="Criterion the issue relates to (for missing coverage)"
    )
    issue_type: str = Field(
        description="missing_scenario | duplicate | weak_steps | wrong_expected | untraceable"
    )
    severity: str = Field(default="medium", description="high | medium | low")
    description: str = Field(min_length=1)
    suggestion: str | None = None


class ReviewOut(BaseModel):
    needs_revision: bool
    findings: list[ReviewFindingOut] = Field(default_factory=list)


# --- Consensus ------------------------------------------------------------
# The Consensus agent responds to each finding bidirectionally: it can *revise*
# (agree and improve), *keep* (rebut/defend the existing case and reject the
# critique, with rationale), or *add* a test case for a genuine missing scenario.


class ConsensusResolutionOut(BaseModel):
    test_case_id: int | None = Field(
        default=None, description="Existing test case addressed; null when adding a new one"
    )
    acceptance_criterion_id: int | None = None
    decision: str = Field(description="revise | keep | add")
    rationale: str = Field(min_length=1, description="Why — the rebuttal or the justification")
    revised_test_case: GeneratedTestCaseOut | None = Field(
        default=None, description="Required for revise/add; omitted for keep"
    )


class ConsensusOut(BaseModel):
    resolutions: list[ConsensusResolutionOut] = Field(default_factory=list)


# --- Prioritizer ----------------------------------------------------------
# The Prioritizer ranks the whole suite by importance and assigns a severity,
# addressing the "priority / severity confusion" that single-pass generation
# leaves unresolved. It annotates existing cases (no new content).


class PriorityRankingOut(BaseModel):
    test_case_id: int
    priority: str = Field(default="medium", description="high | medium | low")
    severity: str = Field(default="major", description="critical | major | minor")
    rank: int = Field(description="1-based importance rank; 1 = most important")
    rationale: str | None = None


class PrioritizationOut(BaseModel):
    rankings: list[PriorityRankingOut] = Field(default_factory=list)


# --- Coverage / Validator -------------------------------------------------
# Coverage of a criterion by test cases is decided deterministically from the
# traceability links (authoritative). The agent adds the semantic judgement:
# is that mapping genuinely adequate, or only superficial?


class CoverageAssessmentOut(BaseModel):
    acceptance_criterion_id: int
    adequate: bool = True
    gap_notes: str | None = None


class CoverageOut(BaseModel):
    assessments: list[CoverageAssessmentOut] = Field(default_factory=list)


# --- Quality --------------------------------------------------------------
# The Quality agent scores each test case on clarity, atomicity, and
# traceability, and flags duplicates — the thesis's Quality Report. Scores are
# 0..1; the engine clamps and aggregates into an overall quality score.


class QualityScoreOut(BaseModel):
    test_case_id: int
    clarity: float = 0.0
    atomicity: float = 0.0
    traceability: float = 0.0
    duplicate: bool = False
    notes: str | None = None


class QualityOut(BaseModel):
    scores: list[QualityScoreOut] = Field(default_factory=list)


# --- Single-LLM baseline --------------------------------------------------
# One prompt, story -> test cases, no acceptance-criterion traceability (the
# baseline's honest limitation). Same shape otherwise, for a fair comparison.


class BaselineTestCaseOut(BaseModel):
    title: str = Field(min_length=1)
    steps: list[str] = Field(min_length=1)
    expected_result: str = Field(min_length=1)
    type: str = Field(default="functional")
    priority: str = Field(default="medium")
    test_data: dict[str, Any] | list[Any] | None = None


class BaselineOut(BaseModel):
    test_cases: list[BaselineTestCaseOut] = Field(default_factory=list)
