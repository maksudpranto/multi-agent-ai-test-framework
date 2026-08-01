"""Consensus agent — the second half of the debate.

Given the Reviewer's findings and the current test cases, the Consensus agent
responds to each finding *bidirectionally*:

- **revise** — it agrees and produces an improved test case (a new version).
- **keep**   — it rebuts the critique and defends the existing case, with a
  rationale explaining why the finding is rejected. This is what makes the
  exchange a debate and not a one-way "apply the review" step.
- **add**    — it accepts a genuine missing-scenario finding and writes a new
  test case for the uncovered criterion.

The agent only produces the resolutions; the engine persists the resulting
`DebateTurn` transcript and versioned `TestCase` rows.
"""
from __future__ import annotations

import json
import time

from pydantic import ValidationError

from app.agents.base import Agent, AgentContext, AgentResult
from app.agents.schemas import ConsensusOut
from app.llm import LLMMessage, LLMService
from app.llm.service import extract_json
from app.models import PipelineStage


class ConsensusAgent(Agent):
    stage = PipelineStage.consensus

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
            findings=json.dumps(inputs.get("findings", [])),
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
            consensus = ConsensusOut.model_validate(extract_json(response.text))
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
            output=consensus.model_dump(),
            metrics=metrics,
            execution_time_ms=int((time.monotonic() - start) * 1000),
            # Hand back to the reviewer for the next round's re-inspection.
            next_action="reviewer",
        )
