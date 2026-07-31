"""Uniform agent contract.

Every stage — requirement analysis, generation, review, consensus, coverage,
quality — is an `Agent` that returns the same `AgentResult`. The orchestrator
only ever handles this one shape, and logging to `AgentExecution` is uniform.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from app.models import PipelineStage


@dataclass
class AgentContext:
    """Everything an agent needs to run one stage, plus config. The engine
    resolves the active prompt and injects its text/id/version here so agents
    stay database-free and testable."""

    inputs: dict[str, Any]
    model: str
    temperature: float = 0.0
    max_tokens: int = 4096
    prompt_template: str | None = None
    prompt_template_id: int | None = None
    prompt_version: str | None = None


@dataclass
class AgentResult:
    stage: PipelineStage
    success: bool
    input: dict[str, Any] = field(default_factory=dict)
    output: dict[str, Any] = field(default_factory=dict)
    reasoning: str | None = None
    metrics: dict[str, Any] = field(default_factory=dict)
    execution_time_ms: int = 0
    next_action: str | None = None
    error: str | None = None


class Agent(ABC):
    """Base class for a single pipeline stage."""

    stage: PipelineStage

    @abstractmethod
    def run(self, ctx: AgentContext) -> AgentResult:
        raise NotImplementedError

    def persist(self, db, run, result: AgentResult) -> None:
        """Write stage-specific artifacts (overridden per stage). Called by the
        engine only on success, inside the run's transaction. Default no-op."""
        return None
