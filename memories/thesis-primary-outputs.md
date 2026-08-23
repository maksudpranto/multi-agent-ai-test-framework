---
name: thesis-primary-outputs
description: "The thesis's canonical agent chain and which outputs are evaluated (primary) vs demonstrated (secondary) — drives build priority"
metadata: 
  node_type: memory
  type: project
  originSessionId: 002ae7a3-c3f4-4716-8731-9b15900f39c5
  modified: 2026-08-02T09:53:53.242Z
---

Project: multi-agent-ai-test-framework (M.Sc thesis, personal GitHub). Repo is a SIBLING of the trip_track working dir at /Volumes/Pranto/SELF/Self_Projects/multi-agent-ai-test-framework.

**Research contribution:** a collaborative multi-agent framework where specialized agents cooperate to produce a *complete software testing package*, improving coverage, traceability, and quality vs a single LLM.

**Canonical agent chain (the evaluated pipeline):**
Requirement → Requirement Agent → Generator Agent → Reviewer Agent → Consensus Agent → Coverage Agent → Quality Agent → Complete Test Design Package.

**Primary outputs — EVALUATED in the thesis. ALL FIVE NOW BUILT:**
- Test Cases ✅ built
- Test Data ✅ built
- Requirement Traceability ✅ built
- Coverage Report ✅ built (Coverage/Validator agent)
- Quality Report ✅ built (Quality agent: clarity/atomicity/traceability scores + duplicate detection; QualityReport rows; UI). The full evaluated agent chain is complete.

**Secondary outputs — demonstrated, NOT deeply evaluated (defer; do not let them compete with primary work):**
Risk Analysis, Preconditions, Test Checklists, API payload suggestions, Security/Performance test suggestions.

**Notes:**
- The Prioritizer agent (priority/severity/rank) is NOT in the canonical chain — treat it as an off-chain secondary extra, not part of the evaluated pipeline.
- The larger 12-section product spec (Modules, multi-type Requirements incl. BRD/PRD/SRS, Export, Research dashboard, Settings) is the eventual product surface; the Module + generalized Requirement data-model refactor was chosen as the "foundation" but deferred in favour of finishing the primary evaluated outputs first.
- Follows [[build-ui-with-functionality]]: every agent ships with its React UI.
