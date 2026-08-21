# Project Handoff — read this first

This file is a self-contained context handoff so a fresh Claude Code session (any account,
any machine) can pick up exactly where we left off. Read it top to bottom before acting.

## Who / what
- **Owner:** M.Sc student, PMIT (Professional Masters in Information Technology), IIT,
  Jahangirnagar University. QA/testing background. Email: maksudpranto.qa@gmail.com.
- **Project:** `multi-agent-ai-test-framework` — an M.Sc thesis prototype.
- **Thesis title (working):** "A Multi-Agent AI Framework for Automated Software Test Case
  Generation and Validation from Software Requirements."
- **Repo:** personal GitHub `git@github.com:maksudpranto/multi-agent-ai-test-framework.git`,
  committed directly to `main`.
- **Note:** the Claude Code working directory is a sibling (`trip_track-main`); ALL thesis work
  lives in `multi-agent-ai-test-framework/`.

## The thesis claim we are building toward
"On an executable benchmark, the multi-agent pipeline detects X% more seeded faults than a
single-LLM baseline (p < 0.05, Wilcoxon), and the Reviewer⇄Consensus debate accounts for Y% of
the gain." The differentiator: we don't ask an LLM if the tests are good — we RUN them against
injected bugs and measure catches (mutation score), with statistical significance.

## Standing principles (always apply)
1. **Build UI with every feature** — never backend-only.
2. **UI must be top-notch, simple, HCI-friendly** (Nielsen heuristics); an examiner should grasp
   results in seconds. No jargon; tooltips for terms like "mutation score"/"p-value".
3. **Quality over quantity** — prefer fewer features, each perfect/industry-standard; cut scope
   to hit that bar. "Done" = production-quality, verified end-to-end, not "it runs".
4. Real AI is wired (Gemini/Groq/OpenRouter) + a deterministic mock provider for $0 runs.

## What is ALREADY BUILT (do not rebuild)
Full working app: auth, projects, requirements; a real multi-agent pipeline —
Requirement-Analysis → Test-Generation → bounded Reviewer⇄Consensus debate (transcript) →
Coverage → Quality → Prioritizer; an LLM-planner Orchestrator with guardrails; a single-LLM
baseline arm; versioned test cases; multi-provider real AI + per-run model picker; a live usage
panel; export (JSON/CSV/MD/XLSX/PDF); "Clean SaaS light" UI. Backend FastAPI + SQLAlchemy +
SQLite + Alembic; frontend React + Vite.

## What is PENDING — the Evaluation Engine + Experiments Dashboard (the thesis proof layer)
Approved plan: `~/.claude/plans/linear-giggling-finch.md`.
- **Phase 1 — DONE (2026-08-21, uncommitted).** Benchmark corpus of 8 Python programs, each with a
  reference oracle + 3 seeded bugs, lives in `backend/app/benchmark/corpus.py` (authoritative) and is
  also materialized to reviewable `backend/app/benchmark/fixtures/` + `manifest.json`.
  `BenchmarkItem`/`BenchmarkMutant` tables + `Experiment.conditions` (JSON) added to `models.py`; one
  Alembic revision `d4e5f6a7b8c9` (applied to dev `app.db`). `benchmark/seed.py::seed_benchmark`
  (idempotent) creates a hidden "Benchmark Suite" project+dataset + one Requirement per item.
  Sandboxed harness in `backend/app/evaluation/harness.py` (+ isolated `_runner.py` worker):
  `materialize_inputs` (LLM → concrete arg-lists, canonical fallback) and `score_suite` →
  `FaultDetectionResult{mutation_score, suite_valid, killed/total, n_usable_inputs, per_mutant}`.
  Reference-as-oracle: a mutant is killed if it diverges (value, exception class, or timeout) on any
  usable input. Verified: `pytest tests/test_harness.py` (12 tests) + full suite 28 passed. Canonical
  inputs kill all mutants; the LLM materializer drives the real per-suite signal (do NOT merge
  canonical into real suites — that would flatten every condition to the same score).
- **Phase 2** `run_full_pipeline` sequencer (honor RunConfig ablation toggles) + experiment runner
  (loop items × conditions: single_llm / full_pipeline / ablation_no_debate) + metrics persisted to
  `ExperimentMetric` + stdlib stats (Wilcoxon + effect size) + one Alembic migration.
- **Phase 3** Evaluation API endpoints (seed benchmark, create/run experiment [background], status,
  results).
- **Phase 4** Experiments dashboard (new sidebar section + list/setup page + results dashboard;
  hand-rolled SVG charts, headline fault-detection, significance callout, CSV/PNG export). Must be
  HCI-friendly per principle 2.
- **Phase 5** Verify: free mock dry-run → real Groq run for actual numbers + pytest.
Key design decisions: reuse existing engine (no agent rewrites); stdlib-only stats (Python 3.14 —
avoid scipy/numpy wheel risk); subprocess sandbox for running buggy code; validate on mock ($0)
first. Effort estimate: ~2–3 focused build sessions.

## Thesis WRITING (deferred until AFTER the build)
- Format: **LaTeX**, university template already downloaded to `thesis/pmit-template/` (main
  `thesis.tex`). IEEE citations (`ieeetr`, numbered), `report` 12pt one-sided 1.5 spacing,
  6 chapters, fixed front-matter order.
- 6-chapter map: 1 Introduction · 2 Background & Literature Review · 3 Proposed Multi-Agent
  Framework · 4 Implementation · 5 Evaluation & Results (needs data) · 6 Conclusion & Future Work.
- Related Work is drafted & paper-grounded: `thesis/related-work-positioning.md`.
- Verified reading list: memory `thesis-related-papers.md`. Closest related work = CANDOR
  (arXiv 2506.02943) and Nexus (arXiv 2510.26423); honest novelty = the COMBINATION
  (requirements-driven + statistically-tested controlled comparison) — NOT "multi-agent" or
  "mutation testing" alone (both already exist in prior work; neither reports significance tests).
- **Metadata still needed for the title page:** full name(s) (possibly a co-author), student ID(s),
  supervisor name+title, submission month/year, final confirmed title.

## Timeline
Target submission ~2nd week of September 2026. Everything runs on **$0** (free tiers + mock).

## EXACT next action when resuming
Phase 1 is done (uncommitted). Next is **Phase 2**: add `run_full_pipeline` (toggle-aware sequencer;
guard `run_debate` with `consensus_enabled`) to `engine.py`; `evaluation/conditions.py` (CONDITIONS
map); `evaluation/runner.py` (loop item × condition, each cell a `PipelineRun(experiment_condition=…)`,
resumable); `evaluation/metrics.py` (→ `ExperimentMetric` rows incl. mutation score via the Phase 1
harness); `evaluation/stats.py` (stdlib Wilcoxon + Cohen's dz + aggregate). Then Phase 3 API, Phase 4
dashboard, Phase 5 verify (mock $0 dry-run → real Groq run). Do NOT start thesis writing until the
build + real experiment results exist (never fabricate numbers).

## On-disk artifacts to copy if moving to a new machine
- `~/.claude/projects/-Volumes-Pranto-SELF-Self-Projects-trip-track-main/memory/` (all memories)
- `~/.claude/plans/linear-giggling-finch.md` (build plan)
- `multi-agent-ai-test-framework/thesis/` (thesis drafts + LaTeX template)
- The git repo itself (code)
