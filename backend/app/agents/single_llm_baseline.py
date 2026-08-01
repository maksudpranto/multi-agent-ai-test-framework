"""Single-LLM baseline — the control arm of the thesis experiment.

One prompt turns the raw user story straight into test cases, with no
requirement-analysis stage, no reviewer, and no consensus debate. This is the
honest baseline the multi-agent framework is measured against: same input, same
output shape, evaluated with the same metrics. Its structural weakness — no
systematic traceability to acceptance criteria — is exactly what the multi-agent
pipeline is hypothesised to improve, so test cases here carry `traces_to=None`.
"""
from __future__ import annotations

import time

from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.agents.base import Agent, AgentContext, AgentResult
from app.agents.schemas import BaselineOut
from app.llm import LLMMessage, LLMService
from app.llm.service import extract_json
from app.models import GeneratedBy, PipelineRun, PipelineStage, TestCase


class SingleLLMBaselineAgent(Agent):
    # Logged under the test_generation stage (it produces test cases); the run's
    # mode=single_llm is what distinguishes it from the multi-agent generator.
    stage = PipelineStage.test_generation

    def __init__(self, llm: LLMService):
        self.llm = llm

    def run(self, ctx: AgentContext) -> AgentResult:
        start = time.monotonic()
        user_story = ctx.inputs.get("user_story", "")
        prompt = (ctx.prompt_template or "").format(user_story=user_story)
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
            baseline = BaselineOut.model_validate(extract_json(response.text))
        except (ValueError, ValidationError) as exc:
            return AgentResult(
                stage=self.stage,
                success=False,
                input={"user_story": user_story},
                metrics=metrics,
                execution_time_ms=int((time.monotonic() - start) * 1000),
                error=f"{type(exc).__name__}: {exc}",
            )

        metrics.update(tokens_in=response.tokens_in, tokens_out=response.tokens_out)
        return AgentResult(
            stage=self.stage,
            success=True,
            input={"user_story": user_story},
            output=baseline.model_dump(),
            metrics=metrics,
            execution_time_ms=int((time.monotonic() - start) * 1000),
        )

    def persist(self, db: Session, run: PipelineRun, result: AgentResult) -> None:
        for test_case in result.output.get("test_cases", []):
            db.add(
                TestCase(
                    pipeline_run_id=run.id,
                    version=1,
                    title=test_case["title"],
                    steps=test_case["steps"],
                    expected_result=test_case["expected_result"],
                    type=test_case.get("type", "functional"),
                    priority=test_case.get("priority", "medium"),
                    traces_to=None,
                    generated_by=GeneratedBy.generator,
                )
            )
