# Project Roadmap & Checklist

Build tracker for the M.Sc thesis project — *A Multi-Agent AI Framework for
Automated Software Test Case Generation and Validation from Software
Requirements.*

Product flow:
`Login → Create Project → Add User Story → Requirement Analysis → Generate Test
Cases → Reviewer Agent → Consensus Agent → Coverage Analysis → Quality
Evaluation → Manual Review → Export`

---

## ✅ Phase 0 — Foundation (DONE)

- [x] Isolated Python venv + personal GitHub repo (SSH, personal account)
- [x] Repo restructure into `backend/` and `frontend/`
- [x] Backend: FastAPI app, config from `.env`, SQLAlchemy engine/session
- [x] Full pipeline DB schema (14 tables) via Alembic migration
- [x] Auth: register / login / me with JWT + bcrypt hashing
- [x] Project CRUD (scoped to logged-in user)
- [x] User Story CRUD (scoped to project)
- [x] Frontend: Vite React app, routing, protected routes, auth context
- [x] UI: Login, Register, Dashboard, Project Detail, User Story Detail
- [x] Pipeline stepper UI (11 steps; stages after "Add User Story" stubbed)
- [x] Verified end-to-end in browser (register → login → project → story → stepper)
- [x] Committed & pushed to GitHub

---

## ⬜ Phase 1 — Requirement Analysis Agent

- [ ] Add `ANTHROPIC_API_KEY` to `backend/.env`
- [ ] Anthropic client wrapper (model config, temperature=0, retries)
- [ ] `AgentExecution` logging plumbing (raw input/output, tokens, latency,
      prompt version) — build this first; every later stage depends on it
- [ ] Pydantic structured-output schema for requirement breakdown
- [ ] Requirement Analysis Agent: user story → actors, preconditions,
      main/alt flows, acceptance criteria, ambiguities
- [ ] `PipelineRun` creation + "Run pipeline" trigger from the UI
- [ ] Persist `AcceptanceCriterion` rows (stable IDs for traceability)
- [ ] UI: show requirement analysis result on the stepper
- [ ] Test with a few sample user stories

## ⬜ Phase 2 — Test Case Generator Agent

- [ ] Structured-output schema for test cases
- [ ] Generator Agent: requirement → test cases, each traced to an
      acceptance criterion (real FK `traces_to`)
- [ ] Write versioned `TestCase` rows (`generated_by = generator`)
- [ ] UI: list generated test cases under the story

## ⬜ Phase 3 — Reviewer Agent

- [ ] Structured-output schema for critiques (issues, suggested fix,
      severity, duplicate flag)
- [ ] Reviewer Agent: test cases + requirement → per-test-case critique
- [ ] Persist critiques as `DebateTurn` (speaker = reviewer)
- [ ] Flag contested test cases (`status = reviewer_flagged`)
- [ ] UI: show reviewer feedback

## ⬜ Phase 4 — Consensus Agent (the core novelty)

- [ ] Bounded debate loop (2–3 rounds): reviewer critiques → generator
      defends/concedes → reviewer re-assesses
- [ ] Log every turn as `DebateTurn`
- [ ] Consensus Agent: reads full transcript, makes independent decision
      (keep / revise / merge / drop) **with a rationale**
- [ ] Create revised `TestCase` versions (`generated_by = consensus`)
- [ ] Record metrics: rounds-to-convergence, reviewer-override rate
- [ ] UI: show debate transcript + consensus decision

## ⬜ Phase 5 — Coverage & Quality

- [ ] Coverage Analysis (deterministic): traceability-matrix join over
      `traces_to` → covered / gaps per acceptance criterion
- [ ] (Optional) LLM pass to flag "superficial" trace links
- [ ] Quality Evaluation (LLM, temperature=0, fixed rubric): clarity,
      atomicity, traceability scores per test case
- [ ] Duplicate detection (embedding similarity; LLM only for ambiguous
      near-duplicates)
- [ ] Persist `CoverageReport` + `QualityReport`
- [ ] UI: coverage matrix + quality scores

## ⬜ Phase 6 — Manual Review

- [ ] Review UI: approve / edit / reject each test case
- [ ] Edits create new `TestCase` versions (`generated_by = manual`)
- [ ] Persist `ManualReview` rows (action, edited content, comment)
- [ ] Status transitions (`manual_approved` / `rejected`)

## ⬜ Phase 7 — Export

- [ ] Export approved test cases to CSV / JSON / XLSX
- [ ] Pin exact `TestCase` versions in `ExportLog` (reproducible exports)
- [ ] UI: download button + export history

## ⬜ Phase 8 — Evaluation Dashboard (thesis chapter)

- [ ] Metrics: coverage %, duplicate rate, rounds-to-consensus, quality
      distributions
- [ ] Single-prompt baseline for comparison (multi-agent vs one prompt)
- [ ] Charts / tables for the thesis writeup
- [ ] Export metrics for the dissertation

---

## Cross-cutting / later

- [ ] "Regenerate" spawns a new `PipelineRun` (`parent_run_id`), never mutates
      an old one — so runs can be diffed
- [ ] Idempotency / run token so retries don't double-call the API
- [ ] Backend unit tests (auth, coverage computation, schema validation)
- [ ] Error handling + retry UI for failed agent stages
- [ ] Deployment (optional): Postgres, hosting, environment config
