"""Prioritizer agent — ranks the test suite by importance.

Single-pass generation leaves every case looking equally important, which is one
of the weaknesses this framework targets ("priority / severity confusion"). The
Prioritizer reads the whole current suite and assigns each case a business
priority, a production-impact severity, and a unique rank. It annotates existing
cases in place (no new content, no new versions) — the change is metadata.
"""
from __future__ import annotations

import json
import time

from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.agents.base import Agent, AgentContext, AgentResult
from app.agents.schemas import PrioritizationOut
from app.llm import LLMMessage, LLMService
from app.llm.service import extract_json
from app.models import PipelineRun, PipelineStage, TestCase


class PrioritizerAgent(Agent):
    stage = PipelineStage.prioritization

    def __init__(self, llm: LLMService):
        self.llm = llm

    def run(self, ctx: AgentContext) -> AgentResult:
        start = time.monotonic()
        user_story = ctx.inputs.get("user_story", "")
        test_cases = ctx.inputs.get("test_cases", [])
        prompt = (ctx.prompt_template or "").format(
            user_story=user_story,
            test_cases=json.dumps(test_cases),
        )
        metrics = {
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
            prioritization = PrioritizationOut.model_validate(extract_json(response.text))
        except (ValueError, ValidationError) as exc:
            return AgentResult(
                stage=self.stage,
                success=False,
                input={"user_story": user_story, "test_cases": test_cases},
                metrics=metrics,
                execution_time_ms=int((time.monotonic() - start) * 1000),
                error=f"{type(exc).__name__}: {exc}",
            )

        metrics.update(tokens_in=response.tokens_in, tokens_out=response.tokens_out)
        return AgentResult(
            stage=self.stage,
            success=True,
            input={"user_story": user_story, "test_cases": test_cases},
            output=prioritization.model_dump(),
            metrics=metrics,
            execution_time_ms=int((time.monotonic() - start) * 1000),
            next_action="coverage",
        )

    def persist(self, db: Session, run: PipelineRun, result: AgentResult) -> None:
        # Annotate existing cases in place: priority, severity, and rank. Only
        # touch cases that belong to this run (guard against stray ids).
        for ranking in result.output.get("rankings", []):
            case = db.get(TestCase, ranking["test_case_id"])
            if case is None or case.pipeline_run_id != run.id:
                continue
            case.priority = ranking.get("priority") or case.priority
            case.severity = ranking.get("severity")
            case.rank = ranking.get("rank")
