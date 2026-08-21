"""Request/response models for the evaluation API.

Kept deliberately thin: the per-condition aggregates and drill-downs are returned
as free-form dicts (straight from ``stats.aggregate_experiment``) so the
dashboard can evolve its charts without a schema migration each time. The typed
models here cover the stable surfaces — creating experiments, listing items, and
status/progress."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel

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


class ExperimentRename(BaseModel):
    name: str


class ExperimentCreate(BaseModel):
    name: str
    dataset_id: int | None = None
    conditions: list[str] | None = None
    # How many times to run the whole grid (averages out LLM run-to-run noise and
    # yields a reproducibility spread). Clamped server-side to a sane range.
    repetitions: int = 1


class ExperimentOut(BaseModel):
    id: int
    name: str
    dataset_id: int | None
    mode: str
    status: str
    conditions: list[str]
    repetitions: int
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
