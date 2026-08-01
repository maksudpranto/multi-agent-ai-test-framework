"""Generate traceable test-case drafts from accepted requirements."""
from __future__ import annotations

import json
import time

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agents.base import Agent, AgentContext, AgentResult
from app.agents.schemas import TestGenerationOut
from app.llm import LLMMessage, LLMService
from app.llm.service import extract_json
from app.models import (
    GeneratedBy,
    PipelineRun,
    PipelineStage,
    TestCase,
    TestCaseStatus,
)


class TestGenerationAgent(Agent):
    """Produces executable test-case drafts linked to source criteria."""

    stage = PipelineStage.test_generation

    def __init__(self, llm: LLMService):
        self.llm = llm

    def run(self, ctx: AgentContext) -> AgentResult:
        start = time.monotonic()
        user_story = ctx.inputs.get("user_story", "")
        criteria = ctx.inputs.get("acceptance_criteria", [])
        prompt = (ctx.prompt_template or "").format(
            user_story=user_story,
            acceptance_criteria=json.dumps(criteria),
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
            generated = TestGenerationOut.model_validate(extract_json(response.text))
        except (ValueError, ValidationError) as exc:
            return AgentResult(
                stage=self.stage,
                success=False,
                input={"user_story": user_story, "acceptance_criteria": criteria},
                metrics=metrics,
                execution_time_ms=int((time.monotonic() - start) * 1000),
                error=f"{type(exc).__name__}: {exc}",
            )

        metrics.update(tokens_in=response.tokens_in, tokens_out=response.tokens_out)
        return AgentResult(
            stage=self.stage,
            success=True,
            input={"user_story": user_story, "acceptance_criteria": criteria},
            output=generated.model_dump(),
            metrics=metrics,
            execution_time_ms=int((time.monotonic() - start) * 1000),
            next_action="reviewer",
        )

    def persist(self, db: Session, run: PipelineRun, result: AgentResult) -> None:
        # The generator produces a full suite (many cases per criterion), so
        # cross-generation versioning by criterion no longer makes sense. Treat
        # each generation as a fresh suite: retire prior *generator* cases that
        # are still live (mark rejected — kept for audit, not deleted) so a
        # re-generation replaces rather than accumulates. Consensus/manual cases
        # are left untouched. New cases are version 1 with no parent; later
        # versions come only from the consensus debate.
        prior = db.scalars(
            select(TestCase).where(
                TestCase.pipeline_run_id == run.id,
                TestCase.generated_by == GeneratedBy.generator,
                TestCase.status != TestCaseStatus.rejected,
            )
        ).all()
        for case in prior:
            case.status = TestCaseStatus.rejected

        for test_case in result.output.get("test_cases", []):
            db.add(
                TestCase(
                    pipeline_run_id=run.id,
                    version=1,
                    parent_test_case_id=None,
                    title=test_case["title"],
                    steps=test_case["steps"],
                    expected_result=test_case["expected_result"],
                    test_data=test_case.get("test_data"),
                    type=test_case["type"],
                    priority=test_case["priority"],
                    traces_to=test_case["acceptance_criterion_id"],
                    generated_by=GeneratedBy.generator,
                )
            )
