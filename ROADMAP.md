# Project Roadmap & Checklist

Build tracker for the M.Sc. thesis project:

> **A Multi-Agent AI Framework for Automated Software Test Case Generation and Validation from Software Requirements**

This repository contains a **research prototype**, not a commercial SaaS product.

The primary research objective is to compare a **Single-LLM baseline** against a **Collaborative Multi-Agent Framework** for automated software test case generation and evaluation.

See [ARCHITECTURE.md](ARCHITECTURE.md) for the complete system architecture.

> ### Why this is agent-based, not a prompt pipeline
> The project is only defensible as *multi-agent* research if it delivers, and measures, four properties — not just N prompts in a row:
> 1. **Specialisation** — distinct role-specific agents (Requirement Analysis, Test Generation, Reviewer, Consensus, Quality).
> 2. **Autonomy** — an agent's output *decides* the next step (see the Agent Autonomy section), rather than a fixed sequential engine.
> 3. **Collaboration** — the **Reviewer ↔ Consensus bounded debate loop** (Phase 4): agents critique, disagree, rebut, and revise across rounds. **This is the core contribution.**
> 4. **Measurable emergence** — the collaboration is measured against the single-LLM baseline (coverage %, duplicate rate, rounds-to-consensus) *and* ablated (with/without debate) to prove the collaboration — not extra prompts — causes the gain.
>
> **Preliminary development uses FREE providers only** — `MockProvider` (offline), **Gemini free tier**, and **Ollama** (local). The paid Claude API is reserved for the *final* thesis evaluation runs, so reported numbers come from one production-grade model. Provider is swapped via `LLM_PROVIDER` with no code changes.

---

# Multi-Agent Pipeline

Input (Requirement **or** Acceptance Criteria — user's choice)
→ Requirement Analysis *(skipped when AC supplied directly)*
→ Test Generation (full suite per criterion: functional / negative / boundary / security / API, each with concrete mock **test data**)
→ Review
→ Consensus
→ Prioritization (priority + severity + rank)
→ Coverage Analysis (traceability matrix + adequacy validation)
→ Quality Evaluation
→ Manual Review
→ Export

Each stage can be executed **independently** during development or as part of the complete pipeline.

**Dual input:** a user can start from a full user story (the Analyzer derives acceptance criteria) **or** paste acceptance criteria directly and skip analysis. Either way, generation, debate, prioritization, and coverage run identically.

---

# 🖥️ Frontend / UI Build Status

Every milestone tracks **two** deliverables: **API** (backend endpoint + persistence + logging) and **UI** (React screen the researcher actually uses). This table is the at-a-glance view; per-phase checklists below carry the detail.

UI strategy: most pipeline stages render into **one shared User-Story run view** (analysis → test cases → review → consensus → coverage/quality as expandable sections) rather than a bespoke page each. Only Manual Review and the Experiment Dashboard are true standalone screens.

| Area | API | UI | UI notes |
|---|---|---|---|
| Auth (login / register) | ✅ | ✅ | Branded split-screen |
| Dashboard | ✅ | ✅ | Real project/story counts |
| Project detail + User Story CRUD | ✅ | ✅ | |
| Pipeline stepper | ✅ | ✅ | Stage status on story page |
| Dual input (Requirement **or** AC-direct) | ✅ | ✅ | Input-mode toggle + AC textarea |
| Requirement Analysis | ✅ | ✅ | Actors/flows/acceptance criteria rendered |
| Test Generation (rich: all types + mock data) | ✅ | ✅ | Full suite per criterion, type badges + test-data blocks |
| Single-LLM baseline + mode switch | ✅ | ✅ | Mode toggle, reuses case cards |
| Review | ✅ | ✅ | Reviewer findings in debate transcript |
| Consensus / debate | ✅ | ✅ | Bounded Reviewer⇄Consensus debate + transcript |
| Prioritization | ✅ | ✅ | Priority + severity + rank; suite ordered by rank |
| Coverage / Validator | ✅ | ✅ | Traceability matrix + % covered + gap notes |
| Quality | ✅ | ✅ | Per-case clarity/atomicity/traceability + duplicates + overall score |
| Manual Review | ❌ | ❌ | Standalone approve/edit/reject screen |
| Export | ❌ | ❌ | Format picker + download |
| Experiment Dashboard | ❌ | ❌ | Standalone comparison charts (thesis eval) |

**Built:** Auth, Dashboard, Project/Story CRUD, Pipeline stepper, **dual input**, Requirement Analysis, **rich multi-agent Test Generation (all test types + mock data)**, Single-LLM baseline + mode switch, Review, Consensus debate, **Prioritization**, **Coverage/Validator**.
**Pending:** Quality Evaluation, Manual Review, Export, Experiment Dashboard.

---

# ✅ Phase 0 — Foundation (DONE)

- [x] Repository structure (`backend/`, `frontend/`)
- [x] Python virtual environment
- [x] FastAPI backend
- [x] SQLAlchemy setup
- [x] JWT Authentication
- [x] Project CRUD
- [x] User Story CRUD
- [x] React application
- [x] Protected routes
- [x] Dashboard
- [x] Project details
- [x] User Story details
- [x] Pipeline stepper
- [x] End-to-end verification

---

# ✅ Phase 0.5 — Research Platform (DONE)

- [x] Dataset table
- [x] PromptTemplate table
- [x] ExperimentConfig
- [x] Experiment
- [x] ExperimentMetric
- [x] PipelineRun improvements
- [x] AgentExecution improvements
- [x] 18-table schema
- [x] ARCHITECTURE.md

---

# ⬜ Phase 1 — AI Foundation

## Infrastructure

- [x] Configurable LLM provider selection (Mock, Anthropic, Gemini, Ollama)
- [x] LLMProvider interface
- [x] Anthropic Provider
- [x] Mock Provider
- [x] Agent base interface
- [x] Workflow Engine
- [x] Pipeline execution manager

## Logging & Reproducibility

- [x] Agent execution logging
- [x] Prompt version tracking
- [x] Raw LLM response storage
- [x] Parsed response storage
- [x] Validated output storage
- [x] Token usage tracking
- [x] Latency tracking
- [ ] Estimated execution cost

## Requirement Analysis Agent

- [x] Prompt template
- [x] Requirement Analysis Agent
- [x] Acceptance Criteria extraction
- [x] Persist RequirementAnalysis
- [x] Persist Acceptance Criteria
- [x] API endpoint
- [x] UI integration

---

# ✅ Phase 2 — Test Generation (DONE)

## Multi-Agent

- [x] Test Generation Agent
- [x] Structured Test Case schema
- [x] Versioned Test Cases
- [x] Traceability mapping

## Baseline

- [x] Single-LLM baseline (API)
- [x] Pipeline mode switching (API)
- [x] UI: mode toggle (single-LLM vs multi-agent)
- [x] UI: generated test cases display

---

# ✅ Phase 3 — AI Review (DONE)

- [x] Review schema (findings persisted as reviewer DebateTurn rows)
- [x] Reviewer Agent
- [x] Missing scenario detection
- [x] Duplicate detection
- [x] Severity classification
- [x] **Revision verdict** — reviewer emits `needs_revision` + per-test-case issues (drives the debate loop; agent decides, engine does not)
- [x] Persist review results
- [x] UI: review findings section (in shared run view)

---

# ✅ Phase 4 — Consensus (DONE)  ⭐ (the agentic core — this is what makes it "multi-agent", not a pipeline)

The debate loop is the thesis's central contribution. These items are what
separate genuine agent collaboration from a one-way "critique-then-apply" step,
so each is spelled out explicitly rather than left to interpretation:

- [x] Consensus Agent
- [x] **Bounded multi-round debate loop** (`max_debate_rounds`, config-driven)
- [x] **Bidirectional exchange** — Consensus agent either *rebuts/defends* a flagged test case (with rationale) OR *revises* it; it does not blindly accept the review
- [x] **Termination condition** — loop ends when the reviewer raises no issues (consensus reached) OR max rounds hit
- [x] **Disagreements + rebuttals persisted** in the DebateTurn transcript (not just final output)
- [x] Test Case revision → new versions (`generated_by=consensus`, `status=consensus_resolved`)
- [x] Consensus rationale
- [x] Consensus metrics (rounds-to-consensus, revisions made, issues resolved)
- [x] UI: debate transcript + consensus visualization (in shared run view)

---

# ✅ Phase 4.5 — Rich generation, dual input, Prioritizer (DONE)

- [x] Dual input: generate from a Requirement **or** from Acceptance Criteria supplied directly (skips analysis)
- [x] Rich generator: full suite per criterion (functional / negative / boundary / security / API)
- [x] Concrete **mock test data** on every case (`test_data`: valid / invalid / boundary values)
- [x] Story-aware offline mock (echoes the actual story, no longer always "login")
- [x] **Prioritizer agent** — assigns priority + severity + unique rank; suite ordered by importance
- [x] Persistence: `TestCase.test_data / severity / rank`, `PipelineRun.input_mode` (Alembic migration)
- [x] UI: input-mode toggle, AC textarea, type/severity/rank badges, test-data blocks, Prioritization section

---

# ✅ Phase 5 — Evaluation (Coverage + Quality DONE) — all 5 primary evaluated outputs complete

## Coverage ✅ DONE

- [x] Requirement Traceability (deterministic matrix over `traces_to` — authoritative)
- [x] Coverage Matrix (per-criterion covered / gap + covering test-case ids)
- [x] Coverage Report (persisted `CoverageReport` rows)
- [x] **Validator adequacy judgement** — agent flags superficial vs genuine coverage (`gap_notes`)
- [x] UI: Coverage section / matrix + % covered (in shared run view)

## Quality ✅ DONE

- [x] Quality Evaluation Agent
- [x] Clarity Score
- [x] Atomicity Score
- [x] Traceability Score
- [x] Duplicate Score (LLM flag + deterministic near-duplicate by title)
- [x] Overall Quality Score

## Persistence

- [x] CoverageReport
- [x] QualityReport

## UI

- [x] UI: Coverage section / matrix (in shared run view)
- [x] UI: Quality scores section / Quality Report (in shared run view)

---

# ⬜ Phase 6 — Manual Review

- [ ] Persist ManualReview (API)
- [ ] UI: Manual Review screen (standalone)
- [ ] UI: Approve
- [ ] UI: Reject
- [ ] UI: Edit
- [ ] UI: Version history

---

# ⬜ Phase 7 — Export

- [ ] CSV Export (API)
- [ ] JSON Export (API)
- [ ] XLSX Export (API)
- [ ] Export history (API)
- [ ] Export version locking (API)
- [ ] UI: export format picker + download

---

# ⬜ Phase 8 — Research & Experiments

## Dataset

- [ ] Dataset Management
- [ ] Dataset Versioning
- [ ] Dataset Import

## Experiment

- [ ] Experiment Manager
- [ ] Experiment Notes
- [ ] Single-LLM execution
- [ ] Multi-Agent execution
- [ ] Batch execution
- [ ] **Baseline parity** — single-LLM baseline uses the same input, output schema, dataset, and metrics as the multi-agent arm (fair comparison, not a strawman)
- [ ] **Ablation** — multi-agent *with* debate loop vs *without*, to show the collaboration (not just "more prompts") causes the improvement

## Metrics

- [ ] Coverage %
- [ ] Duplicate Rate
- [ ] Traceability %
- [ ] Quality Score
- [ ] Execution Time
- [ ] Token Usage
- [ ] Estimated Cost
- [ ] Debate Rounds
- [ ] Consensus Rate

## Dashboard (standalone Experiment Dashboard — thesis evaluation UI)

- [ ] UI: Experiment Comparison
- [ ] UI: Charts
- [ ] UI: Tables
- [ ] UI: Export Results

---

# Agent Autonomy (what makes the agents *agents*, not functions)

Specialisation alone is not agency. At least one agent's **output must decide
what happens next**, rather than the engine running a fixed sequence:

- [x] Wire `AgentResult.next_action` so it drives control flow (reviewer emits consensus/coverage)
- [x] Reviewer decides whether another debate round is needed (`needs_revision`)
- [x] Consensus decides per test case: keep · revise · add _(escalate-to-human: Phase 6)_
- [x] Engine loops/branches on those decisions instead of a hardcoded order

---

# Cross-Cutting Improvements

- [ ] Independent execution of every pipeline stage
- [ ] Pipeline status tracking
- [ ] Pipeline regeneration
- [ ] Retry mechanism
- [ ] Idempotent execution
- [ ] Additional LLM providers
- [ ] Backend unit tests
- [ ] Error handling
- [ ] Deployment

---

# Out of Scope

- Forgot Password

---

# Research Goals

- Compare **Single-LLM** vs **Multi-Agent** approaches
- Improve requirement coverage
- Reduce duplicate test cases
- Improve traceability
- Improve test case quality
- Measure execution cost and latency
- Produce reproducible experimental results

---

# Definition of Done

A milestone is considered complete only if:

- [ ] Backend implemented
- [ ] Frontend integrated
- [ ] Database persistence completed
- [ ] Execution logged
- [ ] Unit tested
- [ ] Manual verification completed
- [ ] Documentation updated

---

# AI Development Strategy (Cost-Optimized)

The system is designed with a provider-independent architecture. All AI agents communicate through a common `LLMProvider` interface, allowing different language models to be used without changing the application logic.

Development will follow a cost-optimized approach:

## Stage 1 — Architecture & Development (Free)

**Provider:** MockProvider

Purpose:
- Develop the complete application architecture
- Build and test the AI workflow
- Verify database persistence
- Test API endpoints
- Validate UI integration
- Debug pipeline execution

No external AI API is required.

---

## Stage 2 — Agent Development (Free)

**Provider:** Google Gemini (Free Tier)

Purpose:
- Develop and refine AI agents
- Test prompt engineering
- Validate structured JSON outputs
- Improve agent collaboration
- Iterate prompts without API cost

---

## Stage 3 — Local Development (Free)

**Provider:** Ollama (Local Models)

Example Models:
- Llama 3.x
- Qwen
- Mistral
- Phi

Purpose:
- Offline development
- Performance testing
- Local experimentation
- Pipeline debugging
- No internet or API cost

---

## Stage 4 — Research Evaluation

**Provider:** Anthropic Claude

Purpose:
- Final thesis experiments
- Benchmark evaluation
- Single-LLM baseline
- Multi-Agent evaluation
- Research paper results
- Dissertation figures and tables

Claude API will only be used during the final evaluation phase to ensure the reported experimental results are generated using the same production-grade model.

---

## Design Principle

All AI providers implement the same interface:

LLMProvider

Supported providers:

- MockProvider
- AnthropicProvider
- GeminiProvider
- OllamaProvider
- OpenAIProvider (Future)

This architecture ensures that AI models can be replaced without modifying the workflow engine or agent implementations.
