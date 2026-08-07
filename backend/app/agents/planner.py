"""The Orchestrator's planner — the agentic control brain.

Given the goal and the live pipeline state, the planner picks which specialist
agent should run next and gives a one-line rationale. It only ever chooses from
the set of *legal* actions the engine hands it (the engine's guardrails enforce
valid transitions, budgets, and stopping), so a bad model choice can never break
the run — this is the "LLM plans, rules guard" hybrid.
"""
from __future__ import annotations

import json

from app.llm import LLMService

ACTION_DESCRIPTIONS = {
    "analyze": "Analyst — break the requirement into a testable spec + acceptance criteria",
    "generate": "Generator — produce a traceable test-case suite from the criteria",
    "debate": "Reviewer ⇄ Consensus — critique and collaboratively revise the suite",
    "coverage": "Validator — build the traceability matrix and judge coverage",
    "quality": "Quality — score clarity/atomicity/traceability and flag duplicates",
    "prioritize": "Prioritizer — rank the suite by importance and severity",
    "finish": "Stop — the goal is met (or the budget is exhausted)",
}


class PlannerAgent:
    def __init__(self, llm: LLMService):
        self.llm = llm

    def decide(self, *, goal: dict, state: dict, legal_actions: list[str], model: str) -> dict:
        """Return {"action", "rationale"}. Action may be empty/invalid — the
        caller validates it against legal_actions and falls back if needed."""
        menu = ", ".join(legal_actions)
        desc = "\n".join(
            f"- {a}: {ACTION_DESCRIPTIONS.get(a, a)}" for a in legal_actions
        )
        prompt = (
            "You are the Orchestrator of a multi-agent software-testing framework. "
            "Each specialist agent owns exactly one task, and you decide which agent "
            "runs next to reach the goal efficiently without wasted work.\n\n"
            f"GOAL: {json.dumps(goal)}\n"
            f"STATE: {json.dumps(state)}\n\n"
            f"Agents you may dispatch this step:\n{desc}\n\n"
            f"CANDIDATE ACTIONS (choose exactly one): {menu}\n"
            'Respond ONLY with JSON: '
            '{"action": "<one candidate>", "rationale": "<one short sentence>"}'
        )
        try:
            parsed, _ = self.llm.complete_json(prompt=prompt, model=model)
            if isinstance(parsed, dict):
                return {
                    "action": str(parsed.get("action", "")).strip(),
                    "rationale": str(parsed.get("rationale", "")).strip(),
                }
        except Exception:
            pass
        return {"action": "", "rationale": ""}
