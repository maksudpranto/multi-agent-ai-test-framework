"""Request/response models for the evaluation API.

Kept deliberately thin: the per-condition aggregates and drill-downs are returned
as free-form dicts (straight from ``stats.aggregate_experiment``) so the
dashboard can evolve its charts without a schema migration each time. The typed
models here cover the stable surfaces — creating experiments, listing items, and
status/progress."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.pipeline.schemas import ModelSelection  # re-exported for the run body


class ConditionOut(BaseModel):
    key: str
    label: str
    description: str
    is_baseline: bool


class BenchmarkSeedResult(BaseModel):
    dataset_id: int
    project_id: int
    n_items: int
    created: int
    refreshed: int


class BenchmarkItemOut(BaseModel):
    id: int
    slug: str
    title: str
    entrypoint: str
    signature: str | None
    requirement_id: int
    n_mutants: int
    is_custom: bool = False
    # True for the built-in programs that make up the default "Quick" subset.
    default_quick: bool = False


# --- Custom (user-authored) benchmark programs ---------------------------


class CustomMutantIn(BaseModel):
    description: str = Field(min_length=1)
    fault_type: str | None = None
    code: str = Field(min_length=1)


class CustomProgramIn(BaseModel):
    title: str = Field(min_length=1)
    entrypoint: str = Field(min_length=1)
    requirement: str = Field(min_length=1)
    reference_code: str = Field(min_length=1)
    canonical_inputs: list[list[Any]] = Field(min_length=1)
    signature: str | None = None
    mutants: list[CustomMutantIn] = Field(min_length=1)


class CustomMutantOut(BaseModel):
    id: int
    mutant_key: str
    description: str | None
    fault_type: str | None
    code: str
    # From the self-check at create time: does this bug actually change the
    # output vs the reference on the given inputs? A "dead" bug (kills=False) can
    # never be caught, so the UI flags it.
    kills: bool | None = None


class CustomProgramOut(BaseModel):
    id: int
    slug: str
    title: str
    entrypoint: str
    signature: str | None
    requirement_id: int
    requirement: str
    reference_code: str
    canonical_inputs: list[list[Any]]
    mutants: list[CustomMutantOut]


class CustomProgramCreated(BaseModel):
    program: CustomProgramOut
    # Warnings surfaced by the self-check (e.g. a bug that doesn't diverge, or a
    # reference that errors on every input).
    warnings: list[str] = Field(default_factory=list)


class ExperimentRename(BaseModel):
    name: str


class ExperimentCreate(BaseModel):
    name: str
    dataset_id: int | None = None
    conditions: list[str] | None = None
    # How many times to run the whole grid (averages out LLM run-to-run noise and
    # yields a reproducibility spread). Clamped server-side to a sane range.
    repetitions: int = 1
    # "full" runs every built-in program; "quick" runs a subset; "custom" runs
    # the user's own programs. Validated server-side.
    scope: str = "full"
    # For "quick": the specific built-in BenchmarkItem ids to run. Empty/None ->
    # the default representative subset.
    item_ids: list[int] | None = None


class ExperimentOut(BaseModel):
    id: int
    name: str
    dataset_id: int | None
    mode: str
    status: str
    conditions: list[str]
    repetitions: int
    scope: str
    item_ids: list[int] | None = None
    created_at: datetime
    completed_at: datetime | None


class ExperimentProgress(BaseModel):
    total: int
    completed: int
    failed: int
    pct: float
    status: str


class ExperimentStatusOut(BaseModel):
    experiment: ExperimentOut
    progress: ExperimentProgress


class RunAccepted(BaseModel):
    experiment_id: int
    status: str
    detail: str
