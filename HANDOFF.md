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

- **Phase 2 — DONE (2026-08-21).** Experiment runner + metrics + stats, all backend, verified on the
  mock provider ($0). `engine.py`: `run_full_pipeline` (toggle-aware sequencer: analyze→generate→
  [debate]→[coverage]→[quality]→prioritize, bracketed stages gated by RunConfig toggles) + `run_debate`
  now honors `consensus_enabled` (skips the revision turn). `evaluation/conditions.py`: `CONDITIONS`
  (single_llm / full_pipeline / ablation_no_debate), `resolve_conditions`, baseline-first ordering.
  `evaluation/metrics.py`: `compute_run_metrics` → `ExperimentMetric` rows (mutation_score + suite_valid
  via Phase 1 harness, coverage %, quality, duplicate rate, rounds-to-consensus, #cases, tokens,
  latency). `evaluation/stats.py`: stdlib `wilcoxon_signed_rank` (normal approx, tie+continuity
  corrected, via math.erf), `cohens_dz`, `rank_biserial`, `describe`, `aggregate_experiment`
  (per-condition summaries + pairwise vs baseline, paired by benchmark item, + headline winner).
  `evaluation/runner.py`: `ExperimentRunner` loops item×condition, resumable (skips scored cells),
  fault-isolating; `run_experiment_task` (own session, for BackgroundTasks); `experiment_progress`.
  NO new migration needed (experiment_condition + conditions already in Phase 1's `d4e5f6a7b8c9`).
  Verified: `pytest tests/test_evaluation.py` (11 tests, incl. a hand-computed Wilcoxon) + full suite
  39 passed. Mock note: all conditions score 1.0 (every suite falls back to canonical inputs → p=1.0);
  differentiation only appears on a real provider — that's expected and correct.

- **Phase 3 — DONE (2026-08-21).** Evaluation API in `backend/app/evaluation/routes.py` (+ `schemas.py`),
  registered in `main.py`. 8 paths / 9 ops, all owner-scoped, mirroring the pipeline routes'
  `Depends(get_db)`/`get_current_user`/`ModelSelection` patterns: `GET /evaluation/conditions`,
  `POST /evaluation/benchmark/seed`, `GET …/datasets/{id}/items`, `GET|POST …/experiments`,
  `POST …/experiments/{id}/run` (202, `BackgroundTasks`→`run_experiment_task`, resumable, 409 if already
  running), `GET …/experiments/{id}` (status+progress), `GET …/experiments/{id}/results`
  (`aggregate_experiment`, returned as free-form dict so the dashboard can add figures without a schema
  change), `GET …/experiments/{id}/items/{requirement_id}` (per-condition drill-down + suites). Verified:
  `pytest tests/test_evaluation_api.py` — full HTTP flow (seed→create→run→poll completed→results→drill)
  on an isolated in-memory DB with the mock engine forced (StaticPool; runner SessionLocal +
  `_resolve_engine_and_model` monkeypatched) + an ownership check. Full suite 41 passed. NB the dev `.env`
  uses `LLM_PROVIDER=gemini`, so offline tests MUST force mock (real runs otherwise hit Gemini 429s).

- **Phase 4 — DONE (2026-08-21), browser-verified.** Experiments dashboard (frontend). `ModelPicker`
  extracted to `components/ModelPicker.jsx` (RequirementDetail now imports it). `api/client.js` +
  evaluation methods (listConditions, seedBenchmark, listBenchmarkItems, listExperiments,
  createExperiment, runExperiment, getExperiment, getExperimentResults, getExperimentItem). Sidebar
  "Research › Experiments" in `AppShell.jsx`; routes `/experiments`, `/experiments/:id` in `App.jsx`.
  `experiments/ExperimentsList.jsx` (seed card, condition pills + ModelPicker, launch = create+run+nav,
  live-polling experiment list). `experiments/ExperimentResults.jsx` (polls while running; headline
  callout, fault-detection tiles with "Best" winner, significance cards, summary table with per-column
  winner highlight, per-program drill-down, CSV + PNG export). Hand-rolled SVG charts in
  `experiments/charts/` (BarChart, GroupedBarChart, palette.js, chartExport.js — svgToPng + downloadCsv).
  Scoped `/* Experiments */` block appended to `index.css`. `npm run lint` clean (warnings only),
  `npm run build` OK. Verified live in-browser end to end on the mock backend (register→login→seed→
  configure→run→completed→results with all sections + drill-down). Mock verify note: to force the free
  mock, run uvicorn with `LLM_PROVIDER=mock` AND clear the stored model (`localStorage.removeItem
  ('matf_model')`) so no real provider selection is sent; `.test` emails are rejected by the validator,
  use a real-looking domain. Demo user `matfdemo2026@example.com` + its experiment now live in the dev
  `app.db`.

## EXACT next action when resuming
Phases 1–4 done — the whole build is functional and browser-verified on mock. Next is **Phase 5**
(verify + real numbers): (a) already have the mock $0 dry-run working; (b) run ONE real study on
**Groq · Llama 3.3 70B** (fast, live free quota) to get actual differentiated numbers — set backend
`LLM_PROVIDER`/keys or just pick Groq in the UI model picker, create an experiment, run it, confirm
multi-agent ≥ baseline on mutation score for a majority of items and ideally a significant Wilcoxon on
at least one comparison; (c) optionally add a couple of pytest cases already covered
(harness/stats/runner/API green — 41 passing). Then update `ROADMAP.md` Phase 8 + `ARCHITECTURE.md`.
The results screen's CSV/PNG exports feed the thesis Evaluation chapter directly. ONLY AFTER real
numbers exist: begin thesis writing (LaTeX, PMIT template in `thesis/`). Never fabricate numbers.

## On-disk artifacts to copy if moving to a new machine
- `~/.claude/projects/-Volumes-Pranto-SELF-Self-Projects-trip-track-main/memory/` (all memories)
- `~/.claude/plans/linear-giggling-finch.md` (build plan)
- `multi-agent-ai-test-framework/thesis/` (thesis drafts + LaTeX template)
- The git repo itself (code)
