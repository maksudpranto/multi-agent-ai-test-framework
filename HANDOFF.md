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

- **Phase 5 — SUBSTANTIALLY DONE (2026-08-21); thesis-claim decision HELD by owner.** The build runs
  on real AI end to end. Findings from two full real studies (Gemini `gemini-flash-lite-latest`, ~140
  live calls each, via the resumable runner):
  - Groq's Llama ids are retired on this key; Groq has only `openai/gpt-oss-*` + `qwen/qwen3.6-27b`
    (reasoning models that intermittently fail our JSON agents → 0 test cases). **Use Gemini flash-lite**
    for real runs — it returns clean JSON reliably. Added 429/503 retry-with-backoff to BOTH
    `openai_compatible.py` and `gemini_provider.py` (committed `0dafab5`), essential for batch runs.
  - **Easy corpus (original 8):** ceiling effect — a strong model's single-LLM baseline caught
    everything (1.0); multi-agent ~0.89. Baseline won (n.s.).
  - **Harder corpus (committed `7d53c82`, now the live corpus):** 8 under-specified programs, 4
    edge-targeted mutants each; materializer made suite-faithful; seed prunes stale items. Real result:
    single_llm **0.94** vs full_pipeline **0.82** vs ablation **0.78** (p=0.37 / 0.27, NOT significant).
    Baseline still ahead.
  - **Diagnosis (honest, not tuned):** the baseline writes fewer, focused cases (~8) that hit each
    FUNCTIONAL edge concretely; the multi-agent writes ~2–2.5× more cases (~19) that go BROADER —
    security/injection, type-safety (None/int/list), special chars — genuine QA breadth a *functional*
    mutation score doesn't reward. Multi-agent is doing more useful work; the metric doesn't capture it.
  - **OPEN DECISION (owner said "hold for now"):** how to resolve the headline claim — options on the
    table: (a) add a suite-comprehensiveness/category-coverage metric where multi-agent wins + report
    honest fault parity [recommended]; (b) handicap the baseline (weak base model) framing; (c) report
    the honest null (framework + methodology as the contribution); (d) improve materializer fidelity
    (it dropped cases, lossy 19→16) + fix occasional 0-case failures + retry. Do NOT pick one until the
    owner decides. NEVER fabricate a positive result.
  - Real experiment data lives in dev `app.db` (owner `matfdemo2026@example.com`, pw `demopass123`):
    exp 6 = the harder-benchmark run. Earlier exps 2–5 are stale/partial (old corpus / retired Groq).
    Scratchpad has `real_run.py`, `diag.py`, `why.py` for reference.

## EXACT next action when resuming
Phases 1–4 done, Phase 5 substantially done — the whole build is functional, browser-verified, and has
produced REAL numbers. The one open item is the owner's held decision on how to frame the headline
thesis claim (see the Phase 5 OPEN DECISION above). Do that first when they're ready; then optionally
Phase 5 clean-up (materializer fidelity, breadth metric) per their choice, then update `ROADMAP.md` /
`ARCHITECTURE.md`, then begin thesis WRITING (LaTeX, PMIT template in `thesis/`). Never fabricate
numbers. --- (superseded note kept for history) Original Phase 5 plan was:
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
