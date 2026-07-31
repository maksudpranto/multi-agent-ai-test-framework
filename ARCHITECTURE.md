# Architecture

This document describes the layered architecture of the framework. The guiding
principle: **this is a research prototype whose implementation must generate
evidence for the thesis experiments** — not just a QA tool. Every layer exists
to make experiments reproducible and comparable (single-LLM baseline vs
multi-agent).

## Layered Overview

```
User
 │
 ▼
Frontend (React)
 │  HTTP/JSON + JWT
 ▼
FastAPI Backend  ──────────────────────────────────────────┐
 │                                                          │
 ▼                                                          │
Workflow Engine  (interface — Default now; LangGraph/       │
 │                CrewAI/AutoGen can drop in later)         │
 ├───────────────────────────┐                             │
 ▼                           ▼                             │
Agent Manager           Experiment Manager                 │
 │  runs stages           │  datasets, configs, modes,      │
 │  in order              │  metrics                        │
 ▼                        ▼                                 │
Requirement Analysis     Metrics / Config                   │
Test Generation                                             │
Review                                                      │
Consensus                                                   │
Coverage (deterministic)                                    │
Quality                                                     │
 │                                                          │
 ▼                                                          │
LLM Service  (provider-agnostic)                            │
 │                                                          │
 ├── AnthropicProvider (now)                                │
 ├── OpenAIProvider    (later)                              │
 ├── GeminiProvider    (later)                              │
 └── MockProvider      (tests / offline)                    │
 │                                                          │
 ▼                                                          │
Claude API                                                  │
                                                            │
SQLite / PostgreSQL  ◀──────────────────────────────────────┘
```

## Why each layer exists

### LLM Service (provider-agnostic)
Agents never call Claude directly. They call `LLMService.complete(...)`, which
delegates to a provider and returns a uniform `LLMResponse` (text, tokens_in,
tokens_out, latency_ms, model). Swapping to GPT/Gemini/Ollama later is a new
provider class, not a rewrite. A `MockProvider` lets the whole pipeline be
tested offline with no API key or cost.

### Agent (uniform result contract)
Every agent — regardless of stage — returns the same `AgentResult`:

```python
AgentResult(
    success: bool,
    input: dict,          # what the agent was given
    output: dict,         # validated structured output
    reasoning: str | None,# model's rationale, for the transcript/audit
    metrics: dict,        # tokens, latency, retries…
    execution_time_ms: int,
    next_action: str | None,  # hint for the orchestrator
)
```

This makes orchestration trivial (the engine only ever handles one shape) and
makes logging to `AgentExecution` uniform.

### Workflow Engine (pluggable orchestration)
The engine decides *which stages run, in what order, under what mode*. It reads
the `ExperimentConfig` (stage toggles) and the run `mode`:

- **`single_llm`** — one LLM call: user story → test cases. The naive baseline.
- **`multi_agent`** — the full collaborative pipeline below.

The engine is defined as an interface (`WorkflowEngine.run(pipeline_run,
config)`) so a future LangGraph/CrewAI/AutoGen implementation is a drop-in
replacement without touching agents or routes.

### Experiment Manager (experiments as first-class)
Because the thesis is fundamentally a comparison, experiments are a top-level
concept. An `Experiment` binds a **Dataset** + **Config** + **Mode**, runs
every story through the engine, and records **Metrics**. Re-running or
comparing single-LLM vs multi-agent is a data operation, not a code change.

## Multi-agent pipeline order

```
Requirement Analysis → Test Generation → Review → Consensus →
Coverage → Quality → Manual Review → Export
```

Coverage and Quality run **after** Consensus, so they measure the final,
reconciled test set (Review/Consensus can still add, revise, merge, or drop
tests before coverage is computed).

## Naming convention

- **UI (end users):** human labels — *Requirement Analysis, Test Generation,
  Review, Consensus, Coverage, Quality Evaluation, Manual Review, Export.*
- **Architecture / code / thesis architecture chapter:** the word *Agent*
  (Requirement Analysis Agent, Reviewer Agent, …). End users don't see it.

## Reproducibility & audit (research-grade)

- **`AgentExecution`** — one row per stage attempt: raw input, raw output,
  reasoning, model, prompt template, tokens, latency, errors.
- **`PromptTemplate`** — prompts are versioned data, not hardcoded strings;
  every execution references the exact template + version used.
- **Versioned `TestCase`** — generator → consensus → manual edits create new
  versions (parent link), preserving lineage.
- **`DebateTurn`** — full Reviewer↔Consensus transcript.
- **`ExperimentMetric`** — precomputed metrics per run and aggregated.
- **Regenerate** spawns a new `PipelineRun` (`parent_run_id`); completed runs
  are immutable so runs can be diffed.

## Data model groups

| Group | Tables |
|-------|--------|
| Identity | `users` |
| Product / authoring | `projects`, `user_stories` |
| Research inputs | `datasets` (groups user stories by domain) |
| Pipeline execution | `pipeline_runs`, `agent_executions` |
| Pipeline artifacts | `acceptance_criteria`, `requirement_analyses`, `test_cases`, `debate_turns`, `coverage_reports`, `quality_reports`, `manual_reviews`, `export_logs` |
| Experiments | `experiments`, `experiment_configs`, `experiment_metrics`, `prompt_templates` |

## Backend package layout (target)

```
backend/app/
├── main.py, config.py, database.py, models.py
├── auth/                # register/login/me, JWT
├── projects/            # project CRUD
├── user_stories/        # user story CRUD
├── datasets/            # dataset CRUD (research inputs)          [later]
├── experiments/         # experiment + config CRUD, run trigger  [later]
├── llm/                 # base provider ABC, anthropic, mock, service
├── agents/              # base (AgentResult), schemas, one module per stage
├── workflow/            # engine interface + default engine
└── prompts/             # seed prompt templates into the DB
```
