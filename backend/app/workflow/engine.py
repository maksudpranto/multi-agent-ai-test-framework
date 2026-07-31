"""Workflow orchestration.

`WorkflowEngine` is an interface so a future LangGraph/CrewAI/AutoGen engine can
replace `DefaultWorkflowEngine` without touching agents or routes. The default
engine runs one stage at a time, logs an `AgentExecution` row for every attempt,
and lets each agent persist its own artifacts.

As of Phase 1 only the requirement-analysis stage is registered; later phases
register the remaining agents and flesh out full sequential `run()`.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from sqlalchemy.orm import Session

from app.agents.base import Agent, AgentContext, AgentResult
from app.llm import LLMService, get_llm_service
from app.models import (
    AgentExecution,
    ExecutionStatus,
    PipelineRun,
    PipelineStage,
)
from app.prompts.seed import get_active_prompt
from app.workflow.config import RunConfig


class WorkflowEngine(ABC):
    @abstractmethod
    def run_stage(
        self,
        db: Session,
        run: PipelineRun,
        stage: PipelineStage,
        inputs: dict[str, Any],
        config: RunConfig,
    ) -> AgentResult:
        raise NotImplementedError


class DefaultWorkflowEngine(WorkflowEngine):
    def __init__(self, llm_service: LLMService | None = None):
        self.llm = llm_service or get_llm_service()

    def _agent_for(self, stage: PipelineStage) -> Agent:
        # Imported here to avoid a circular import (agents import the engine's
        # config type). Extended per phase as new agents are added.
        if stage == PipelineStage.requirement_analysis:
            from app.agents.requirement_analysis import RequirementAnalysisAgent

            return RequirementAnalysisAgent(self.llm)
        if stage == PipelineStage.test_generation:
            from app.agents.test_generation import TestGenerationAgent

            return TestGenerationAgent(self.llm)
        raise NotImplementedError(f"No agent registered for stage {stage.value}")

    def run_stage(
        self,
        db: Session,
        run: PipelineRun,
        stage: PipelineStage,
        inputs: dict[str, Any],
        config: RunConfig,
    ) -> AgentResult:
        agent = self._agent_for(stage)

        attempt_no = (
            db.query(AgentExecution)
            .filter(
                AgentExecution.pipeline_run_id == run.id,
                AgentExecution.stage == stage,
            )
            .count()
            + 1
        )

        prompt = get_active_prompt(db, stage)
        if prompt is None:
            raise RuntimeError(
                f"No active prompt template seeded for stage {stage.value}"
            )

        ctx = AgentContext(
            inputs=inputs,
            model=config.model,
            temperature=config.temperature,
            max_tokens=config.max_tokens,
            prompt_template=prompt.template,
            prompt_template_id=prompt.id,
            prompt_version=prompt.version,
        )
        result = agent.run(ctx)

        # Audit trail: one row per attempt, regardless of success.
        execution = AgentExecution(
            pipeline_run_id=run.id,
            stage=stage,
            attempt_no=attempt_no,
            raw_input=result.input or inputs,
            raw_output=result.output,
            reasoning=result.reasoning,
            model=result.metrics.get("model"),
            prompt_template_id=result.metrics.get("prompt_template_id"),
            prompt_version=result.metrics.get("prompt_version"),
            tokens_in=result.metrics.get("tokens_in"),
            tokens_out=result.metrics.get("tokens_out"),
            latency_ms=result.execution_time_ms,
            status=ExecutionStatus.success if result.success else ExecutionStatus.failed,
            error=result.error,
        )
        db.add(execution)
        db.flush()

        # Stage-specific persistence (e.g. RequirementAnalysis rows).
        if result.success:
            agent.persist(db, run, result)

        db.commit()
        return result
