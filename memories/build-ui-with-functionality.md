---
name: build-ui-with-functionality
description: "Every functionality must ship with its corresponding UI, not backend-only"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 002ae7a3-c3f4-4716-8731-9b15900f39c5
  modified: 2026-07-31T13:21:48.641Z
---

For the multi-agent-ai-test-framework thesis project, whenever building a functionality, build the corresponding UI along with it in the same pass — never deliver a backend/API endpoint without its React screen.

**Why:** The user is the researcher who drives experiments through the UI; a stage that only exists as an API can't actually be used or demoed for the thesis. The ROADMAP explicitly tracks API vs UI as two separate deliverables per milestone (Definition of Done includes "Frontend integrated").

**How to apply:** For each pipeline stage / feature, implement backend + persistence + logging AND the React UI. Most pipeline stages render into the shared User-Story run view (analysis → test cases → review → consensus → coverage/quality as sections); Manual Review and the Experiment Dashboard are standalone screens. Update both the API and UI checkboxes in ROADMAP.md when done.
