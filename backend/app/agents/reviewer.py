"""Reviewer agent — critiques the current test cases.

The Reviewer is the first half of the multi-agent debate. It inspects the
current set of generated test cases against the user story and acceptance
criteria and reports concrete findings (missing scenarios, duplicates, weak
steps, wrong expectations, broken traceability) with a severity each.

Its `needs_revision` verdict is the point of agent autonomy: the engine loops
into a Consensus round only because the Reviewer said so, and terminates the
debate the moment the Reviewer is satisfied. The engine never makes that call.
"""
from __future__ import annotations

import json
import time

from pydantic import ValidationError

from app.agents.base import Agent, AgentContext, AgentResult
from app.agents.schemas import ReviewOut
from app.llm import LLMMessage, LLMService
from app.llm.service import extract_json
from app.models import PipelineStage


class ReviewerAgent(Agent):
    stage = PipelineStage.reviewer

    def __init__(self, llm: LLMService):
        self.llm = llm

    def run(self, ctx: AgentContext) -> AgentResult:
        start = time.monotonic()
        inputs = ctx.inputs
        prompt = (ctx.prompt_template or "").format(
            round=inputs.get("round", 1),
            user_story=inputs.get("user_story", ""),
            acceptance_criteria=json.dumps(inputs.get("acceptance_criteria", [])),
            test_cases=json.dumps(inputs.get("test_cases", [])),
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
            review = ReviewOut.model_validate(extract_json(response.text))
        except (ValueError, ValidationError) as exc:
            return AgentResult(
                stage=self.stage,
                success=False,
                input=inputs,
                metrics=metrics,
                execution_time_ms=int((time.monotonic() - start) * 1000),
                error=f"{type(exc).__name__}: {exc}",
            )

        metrics.update(tokens_in=response.tokens_in, tokens_out=response.tokens_out)
        return AgentResult(
            stage=self.stage,
            success=True,
            input=inputs,
            output=review.model_dump(),
            metrics=metrics,
            execution_time_ms=int((time.monotonic() - start) * 1000),
            # Autonomy: the reviewer's verdict decides whether the debate goes on.
            next_action="consensus" if review.needs_revision else "coverage",
        )
