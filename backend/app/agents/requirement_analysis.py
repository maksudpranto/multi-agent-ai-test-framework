from __future__ import annotations

import time

from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.agents.base import Agent, AgentContext, AgentResult
from app.agents.schemas import RequirementAnalysisOut
from app.llm import LLMMessage, LLMService
from app.llm.service import extract_json
from app.models import (
    AcceptanceCriterion,
    PipelineRun,
    PipelineStage,
    RequirementAnalysis,
)


class RequirementAnalysisAgent(Agent):
    """Turns a raw user story into a structured, testable specification."""

    stage = PipelineStage.requirement_analysis

    def __init__(self, llm: LLMService):
        self.llm = llm

    def run(self, ctx: AgentContext) -> AgentResult:
        start = time.monotonic()
        user_story = ctx.inputs.get("user_story", "")
        prompt = (ctx.prompt_template or "").format(user_story=user_story)

        base_metrics = {
            "model": ctx.model,
            "prompt_template_id": ctx.prompt_template_id,
            "prompt_version": ctx.prompt_version,
        }

        try:
            response = self.llm.complete(
                messages=[LLMMessage(role="user", content=prompt)],
                model=ctx.model,
                temperature=ctx.temperature,
                max_tokens=ctx.max_tokens,
            )
            parsed = extract_json(response.text)
            analysis = RequirementAnalysisOut.model_validate(parsed)
        except (ValueError, ValidationError) as exc:
            return AgentResult(
                stage=self.stage,
                success=False,
                input={"user_story": user_story},
                metrics=base_metrics,
                execution_time_ms=int((time.monotonic() - start) * 1000),
                error=f"{type(exc).__name__}: {exc}",
            )

        base_metrics.update(
            tokens_in=response.tokens_in, tokens_out=response.tokens_out
        )
        return AgentResult(
            stage=self.stage,
            success=True,
            input={"user_story": user_story},
            output=analysis.model_dump(),
            metrics=base_metrics,
            execution_time_ms=int((time.monotonic() - start) * 1000),
            next_action="test_generation",
        )

    def persist(self, db: Session, run: PipelineRun, result: AgentResult) -> None:
        out = result.output
        db.add(
            RequirementAnalysis(
                pipeline_run_id=run.id,
                actors=out.get("actors"),
                preconditions=out.get("preconditions"),
                main_flow=out.get("main_flow"),
                alt_flows=out.get("alt_flows"),
                ambiguities=out.get("ambiguities"),
            )
        )
        for order, ac in enumerate(out.get("acceptance_criteria", [])):
            db.add(
                AcceptanceCriterion(
                    pipeline_run_id=run.id,
                    text=ac.get("text", ""),
                    order=order,
                )
            )
