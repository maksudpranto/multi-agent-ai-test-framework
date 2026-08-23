---
name: agentic-orchestrator
description: "The thesis's agentic core — an LLM-planner Orchestrator that drives specialist agents under guardrails"
metadata: 
  node_type: memory
  type: project
  originSessionId: 002ae7a3-c3f4-4716-8731-9b15900f39c5
  modified: 2026-08-07T04:36:10.713Z
---

The thesis must be genuinely **agentic** (user's explicit goal). The system was a fixed prompt-chain + one debate loop; it now has an agentic control layer: **each task has its own specialist agent** (Analyst, Generator, Reviewer⇄Consensus, Prioritizer, Validator/Coverage, Quality) and an **Orchestrator** decides which runs next.

**Design = "LLM plans, rules guard" (hybrid)** — chosen as best for a thesis: genuine agency (model-driven control) + reproducible/bounded (guardrails) + runs offline on the mock.
- `backend/app/agents/planner.py` — `PlannerAgent.decide(goal, state, legal_actions, model)` returns `{action, rationale}` via `llm.complete_json`. Prompt marker "You are the Orchestrator"; mock branch in `llm/service.py` returns the first legal candidate so it works offline.
- `backend/app/workflow/engine.py` — `run_orchestration()` loop: snapshot state (`_orch_state`), compute legal moves (`_orch_legal` guardrails: valid transitions, no loops, step budget), planner picks (invalid→fallback to first legal), dispatch to existing engine methods (`_orch_dispatch`), log each decision as `AgentExecution(stage=planning)` — that ordered log IS the auditable agency trace.
- New enum value `PipelineStage.planning` (VARCHAR → no migration).
- `POST /projects/{id}/requirements/{id}/orchestrate` → returns decision trace + coverage/quality/suite. Frontend: `api.orchestrate()`, an "Autonomous agent · Orchestrator" card on the RequirementDetail **Overview** tab renders the decision timeline (`OrchestrationTrace`). Contrasts with the fixed "Run full pipeline".

Verified offline: 7 decisions (analyze→generate→debate→coverage→quality→prioritize→finish), 100% coverage, 16 backend tests pass. Commits 2c4abab (backend) + ae84ad1 (UI).

**Next agentic increments (tasks #35):** Executor agent = execution-grounded validation (emit runnable tests + actually run them, feed failures back) — the other big novelty, closes the "Generation AND Validation" title. Also possible: closed-loop gap-driven regeneration, memory/RAG. The defensible thesis contribution is an ablation study: single-LLM vs fixed-pipeline vs agentic-orchestrator on coverage/duplicate-rate/quality/tokens/cost. See [[thesis-primary-outputs]].
