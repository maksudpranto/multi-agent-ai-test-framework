"""Generate concrete sample data for a single test case, on demand.

The Generator writes the suite and can include `test_data` inline, but a user
often wants to fill in (or improve) the data for one specific case after the
fact. This agent takes one existing test case plus the requirement it came from
and returns realistic, executable data — valid, invalid, and boundary values —
matching the case's domain and type. The route persists the result onto the
case; this agent stays database-free.
"""
from __future__ import annotations

import json
import time

from pydantic import ValidationError

from app.agents.base import Agent, AgentContext, AgentResult
from app.agents.schemas import TestDataOut
from app.llm import LLMMessage, LLMService
from app.llm.service import extract_json
from app.models import PipelineStage


class TestDataAgent(Agent):
    """Produces concrete mock/sample data for one test case."""

    stage = PipelineStage.test_data

    def __init__(self, llm: LLMService):
        self.llm = llm

    def run(self, ctx: AgentContext) -> AgentResult:
        start = time.monotonic()
        user_story = ctx.inputs.get("user_story", "")
        test_case = ctx.inputs.get("test_case", {})
        prompt = (ctx.prompt_template or "").format(
            user_story=user_story,
            test_case=json.dumps(test_case, indent=2),
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
            generated = TestDataOut.model_validate(extract_json(response.text))
        except (ValueError, ValidationError) as exc:
            return AgentResult(
                stage=self.stage,
                success=False,
                input={"test_case": test_case},
                metrics=metrics,
                execution_time_ms=int((time.monotonic() - start) * 1000),
                error=f"{type(exc).__name__}: {exc}",
            )

        metrics.update(tokens_in=response.tokens_in, tokens_out=response.tokens_out)
        return AgentResult(
            stage=self.stage,
            success=True,
            input={"test_case": test_case},
            output=generated.model_dump(),
            metrics=metrics,
            execution_time_ms=int((time.monotonic() - start) * 1000),
        )
