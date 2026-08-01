"""Coverage / Validator agent — confirms requirement coverage.

Whether a criterion is *traced* to at least one test case is decided
deterministically from the traceability links (see the engine). This agent adds
the judgement a matrix cannot: is that coverage genuinely ADEQUATE, or only
superficial (happy-path only, missing negative/boundary)? That semantic check is
what turns a traceability matrix into a validation step.

The engine passes in the already-computed coverage map, runs this agent for the
adequacy judgement, then writes CoverageReport rows itself (merging the
deterministic mapping with these assessments).
"""
from __future__ import annotations

import json
import time

from pydantic import ValidationError

from app.agents.base import Agent, AgentContext, AgentResult
from app.agents.schemas import CoverageOut
from app.llm import LLMMessage, LLMService
from app.llm.service import extract_json
from app.models import PipelineStage


class CoverageAgent(Agent):
    stage = PipelineStage.coverage

    def __init__(self, llm: LLMService):
        self.llm = llm

    def run(self, ctx: AgentContext) -> AgentResult:
        start = time.monotonic()
        user_story = ctx.inputs.get("user_story", "")
        coverage_map = ctx.inputs.get("coverage_map", [])
        prompt = (ctx.prompt_template or "").format(
            user_story=user_story,
            coverage_map=json.dumps(coverage_map),
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
            coverage = CoverageOut.model_validate(extract_json(response.text))
        except (ValueError, ValidationError) as exc:
            return AgentResult(
                stage=self.stage,
                success=False,
                input={"user_story": user_story, "coverage_map": coverage_map},
                metrics=metrics,
                execution_time_ms=int((time.monotonic() - start) * 1000),
                error=f"{type(exc).__name__}: {exc}",
            )

        metrics.update(tokens_in=response.tokens_in, tokens_out=response.tokens_out)
        return AgentResult(
            stage=self.stage,
            success=True,
            input={"user_story": user_story, "coverage_map": coverage_map},
            output=coverage.model_dump(),
            metrics=metrics,
            execution_time_ms=int((time.monotonic() - start) * 1000),
            next_action="quality",
        )
