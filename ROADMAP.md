# Project Roadmap & Checklist

Build tracker for the M.Sc. thesis project:

> **A Multi-Agent AI Framework for Automated Software Test Case Generation and Validation from Software Requirements**

This repository contains a **research prototype**, not a commercial SaaS product.

The primary research objective is to compare a **Single-LLM baseline** against a **Collaborative Multi-Agent Framework** for automated software test case generation and evaluation.

See [ARCHITECTURE.md](ARCHITECTURE.md) for the complete system architecture.

---

# Multi-Agent Pipeline

Requirement Analysis
→ Test Generation
→ Review
→ Consensus
→ Coverage Analysis
→ Quality Evaluation
→ Manual Review
→ Export

Each stage can be executed **independently** during development or as part of the complete pipeline.

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
- [ ] Agent base interface
- [ ] Workflow Engine
- [ ] Pipeline execution manager

## Logging & Reproducibility

- [ ] Agent execution logging
- [ ] Prompt version tracking
- [ ] Raw LLM response storage
- [ ] Parsed response storage
- [ ] Validated output storage
- [ ] Token usage tracking
- [ ] Latency tracking
- [ ] Estimated execution cost

## Requirement Analysis Agent

- [ ] Prompt template
- [ ] Requirement Analysis Agent
- [ ] Acceptance Criteria extraction
- [ ] Persist RequirementAnalysis
- [ ] Persist Acceptance Criteria
- [ ] API endpoint
- [ ] UI integration

---

# ⬜ Phase 2 — Test Generation

## Multi-Agent

- [ ] Test Generation Agent
- [ ] Structured Test Case schema
- [ ] Versioned Test Cases
- [ ] Traceability mapping

## Baseline

- [ ] Single-LLM baseline
- [ ] Pipeline mode switching
- [ ] UI for generated test cases

---

# ⬜ Phase 3 — AI Review

- [ ] Review schema
- [ ] Reviewer Agent
- [ ] Missing scenario detection
- [ ] Duplicate detection
- [ ] Severity classification
- [ ] Persist review results
- [ ] Review UI

---

# ⬜ Phase 4 — Consensus

- [ ] Debate workflow
- [ ] Debate transcript
- [ ] Consensus Agent
- [ ] Test Case revision
- [ ] Consensus rationale
- [ ] Consensus metrics
- [ ] UI visualization

---

# ⬜ Phase 5 — Evaluation

## Coverage

- [ ] Requirement Traceability
- [ ] Coverage Matrix
- [ ] Coverage Report

## Quality

- [ ] Quality Evaluation Agent
- [ ] Clarity Score
- [ ] Atomicity Score
- [ ] Traceability Score
- [ ] Duplicate Score
- [ ] Overall Quality Score

## Persistence

- [ ] CoverageReport
- [ ] QualityReport

## UI

- [ ] Coverage Dashboard
- [ ] Quality Dashboard

---

# ⬜ Phase 6 — Manual Review

- [ ] Manual Review UI
- [ ] Approve
- [ ] Reject
- [ ] Edit
- [ ] Version history
- [ ] Persist ManualReview

---

# ⬜ Phase 7 — Export

- [ ] CSV Export
- [ ] JSON Export
- [ ] XLSX Export
- [ ] Export history
- [ ] Export version locking

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

## Dashboard

- [ ] Experiment Comparison
- [ ] Charts
- [ ] Tables
- [ ] Export Results

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
