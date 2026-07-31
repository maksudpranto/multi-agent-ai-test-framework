# Project Roadmap & Checklist

Build tracker for the M.Sc thesis project — *A Multi-Agent AI Framework for
Automated Software Test Case Generation and Validation from Software
Requirements.*

This is a **research prototype**: experiments (single-LLM baseline vs
multi-agent) are a first-class concept. See [ARCHITECTURE.md](ARCHITECTURE.md)
for the layered design.

Multi-agent pipeline order:
`Requirement Analysis → Test Generation → Review → Consensus → Coverage →
Quality → Manual Review → Export` (Coverage/Quality run after Consensus).

---

## ✅ Phase 0 — Foundation (DONE)

- [x] Isolated Python venv + personal GitHub repo (SSH)
- [x] Repo restructure into `backend/` and `frontend/`
- [x] Backend: FastAPI, config from `.env`, SQLAlchemy engine/session
- [x] Auth: register / login / me with JWT + bcrypt
- [x] Project CRUD + User Story CRUD (scoped)
- [x] React app: routing, protected routes, auth context, dashboard,
      project detail, user story detail, pipeline stepper
- [x] Verified end-to-end in browser, committed & pushed

## ✅ Phase 0.5 — Research-platform schema + architecture (DONE)

- [x] `Dataset` table (groups user stories by domain) + `dataset_id` on story
- [x] `PromptTemplate` table (versioned prompts as data)
- [x] `ExperimentConfig` (model, temperature, max_tokens, stage toggles,
      debate rounds)
- [x] `Experiment` (dataset + config + mode: single_llm / multi_agent)
- [x] `ExperimentMetric` (precomputed metrics per run + aggregate)
- [x] `PipelineRun.mode` + `experiment_id`; `AgentExecution.prompt_template_id`
      + `reasoning`
- [x] Clean single migration (18 tables) applied
- [x] `ARCHITECTURE.md` documenting the layered design

---

## ⬜ Phase 1 — Foundations for agents (LLM Service, Engine, first stage)

- [ ] Add `ANTHROPIC_API_KEY` to `backend/.env`
- [ ] **LLM Service:** `LLMProvider` ABC + `LLMResponse` (tokens/latency/model)
- [ ] `AnthropicProvider` + `MockProvider` (offline / no-cost testing)
- [ ] **Agent base:** uniform `AgentResult` contract + `Agent` ABC
- [ ] **Workflow Engine:** `WorkflowEngine` interface + `DefaultWorkflowEngine`
      (reads config + mode); pluggable for LangGraph/CrewAI later
- [ ] `AgentExecution` logging plumbing (raw I/O, reasoning, tokens, latency,
      prompt template + version)
- [ ] `PromptTemplate` seeding for the requirement-analysis stage
- [ ] **Requirement Analysis Agent:** story → actors, preconditions,
      main/alt flows, acceptance criteria, ambiguities (Pydantic-validated)
- [ ] Persist `RequirementAnalysis` + `AcceptanceCriterion` rows
- [ ] API endpoint + "Run Requirement Analysis" trigger in the UI
- [ ] Verify with MockProvider (and real key if set)

## ⬜ Phase 2 — Test Generation + Single-LLM baseline

- [ ] Test-case structured-output schema
- [ ] Test Generation Agent: requirement → test cases, each with real FK
      `traces_to` an acceptance criterion; versioned `TestCase` rows
- [ ] **Single-LLM baseline mode:** one call, story → test cases (no analysis,
      no review/consensus) — the comparison target
- [ ] Engine branches on `mode` (single_llm vs multi_agent)
- [ ] UI: list generated test cases

## ⬜ Phase 3 — Review

- [ ] Critique schema (issues, suggested fix, severity, duplicate flag)
- [ ] Reviewer Agent: test cases + requirement → per-test critique
- [ ] Persist as `DebateTurn` (speaker = reviewer); flag contested tests
- [ ] UI: show review feedback

## ⬜ Phase 4 — Consensus (core novelty)

- [ ] Bounded debate loop (config `max_debate_rounds`): reviewer → generator
      defends/concedes → reviewer re-assesses
- [ ] Log every turn as `DebateTurn`
- [ ] Consensus Agent: reads full transcript, independent decision
      (keep/revise/merge/drop) **with rationale**
- [ ] Revised `TestCase` versions (`generated_by = consensus`)
- [ ] Metrics: rounds-to-convergence, reviewer-override rate
- [ ] UI: debate transcript + consensus decision

## ⬜ Phase 5 — Coverage & Quality

- [ ] Coverage (deterministic): traceability-matrix join over `traces_to`
- [ ] Quality (LLM, temperature=0, fixed rubric): clarity, atomicity,
      traceability scores
- [ ] Duplicate detection (embedding similarity; LLM for ambiguous cases)
- [ ] Persist `CoverageReport` + `QualityReport`
- [ ] UI: coverage matrix + quality scores

## ⬜ Phase 6 — Manual Review

- [ ] Review UI: approve / edit / reject per test case
- [ ] Edits create new `TestCase` versions (`generated_by = manual`)
- [ ] Persist `ManualReview`; status transitions

## ⬜ Phase 7 — Export

- [ ] Export approved test cases to CSV / JSON / XLSX
- [ ] Pin exact `TestCase` versions in `ExportLog`
- [ ] UI: download + export history

## ⬜ Phase 8 — Experiment Manager + Evaluation Dashboard

- [ ] Dataset CRUD UI (import stories, tag domain)
- [ ] Experiment Config UI (model, temperature, stage toggles, mode)
- [ ] Create/run Experiment over a dataset; batch runs
- [ ] Compute + store `ExperimentMetric` (coverage %, duplicate rate,
      quality, traceability, rounds-to-consensus, execution time)
- [ ] Results dashboard: single-LLM vs multi-agent comparison, charts/tables
- [ ] Home dashboard stat tiles (projects, stories, tests, coverage, quality)
      + recent activity
- [ ] Export metrics for the dissertation

---

## Cross-cutting / later

- [ ] Regenerate = new `PipelineRun` (`parent_run_id`), never mutate old runs
- [ ] Idempotency / run token so retries don't double-call the API
- [ ] Additional LLM providers (OpenAI, Gemini, Ollama) behind LLM Service
- [ ] Backend unit tests (auth, coverage computation, schema validation)
- [ ] Error handling + retry UI for failed stages
- [ ] Deployment (optional): Postgres, hosting, env config

## Explicitly out of scope (not research-relevant)

- Forgot-password, email verification, refresh tokens
