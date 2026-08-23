---
name: ui-must-be-hci-friendly
description: "Standing UI requirement — every screen must be top-notch, simple, and HCI-compliant; no complexity exposed to the user"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 002ae7a3-c3f4-4716-8731-9b15900f39c5
  modified: 2026-08-15T13:23:05.511Z
---

Every UI in this project must be **top-notch, super user-friendly, and easy to understand** —
no complex or intimidating interfaces. Follow HCI principles (Nielsen heuristics): clear visibility
of system status, plain language (no jargon), recognition over recall, minimalist design, good
feedback, error prevention, sensible defaults, and consistency with the existing "Clean SaaS light"
aesthetic.

**Why:** This is an M.Sc thesis prototype that will be demoed/defended; a confusing UI undermines
the work regardless of how strong the backend is. The user explicitly wants ease-of-use as a
first-class quality, not an afterthought.

**How to apply:**
- Especially the new Experiments/Evaluation dashboard ([[thesis-writing-plan]] build): a
  non-technical viewer (e.g. an examiner) should understand "which approach caught more bugs and
  by how much" in seconds — big plain-language headline numbers, one clear winner highlight, a
  simple significance sentence ("+23% more bugs, statistically significant"), tooltips explaining
  any term (mutation score, p-value).
- Prefer guided one-click flows (e.g. "Run experiment") over multi-step config; sensible defaults
  preselected.
- Match existing components (stat tiles, gauge cards, chips, segmented toggles); keep charts clean
  with labelled axes + legend.
- Every action gives visible feedback (progress bars, spinners, status chips).
- Relates to [[build-ui-with-functionality]] (every feature ships with its UI).
