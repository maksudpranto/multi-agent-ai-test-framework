"""Quality agent — the terminal evaluation agent.

Scores each test case on clarity, atomicity, and traceability, and flags
duplicates. This is the thesis's Quality Report: the last of the five primary
evaluated outputs (test cases, test data, traceability, coverage, quality).

The engine runs this agent for the judgement, then writes QualityReport rows
(merging a deterministic near-duplicate pass with the agent's scores).
"""
from __future__ import annotations

import json
import time

from pydantic import ValidationError

from app.agents.base import Agent, AgentContext, AgentResult
from app.agents.schemas import QualityOut
from app.llm import LLMMessage, LLMService
from app.llm.service import extract_json
from app.models import PipelineStage


class QualityAgent(Agent):
    stage = PipelineStage.quality

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
            quality = QualityOut.model_validate(extract_json(response.text))
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
            output=quality.model_dump(),
            metrics=metrics,
            execution_time_ms=int((time.monotonic() - start) * 1000),
        )
