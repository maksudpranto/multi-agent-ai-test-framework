---
name: quality-over-quantity
description: "Standing scope principle — prefer fewer features, but everything built must be perfect, industry-standard, and top-notch"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 002ae7a3-c3f4-4716-8731-9b15900f39c5
  modified: 2026-08-15T13:24:38.981Z
---

Prefer **fewer features** over many. Whatever IS built must be **perfect, industry-standard, and
top-notch** — polished, robust, and complete, not a broad set of half-done things. It is fine to
**cut or defer scope** to hit that bar.

**Why:** M.Sc thesis prototype that will be demoed and defended. A small number of flawless,
credible features is more defensible and more impressive than feature breadth with rough edges.
The user explicitly values depth/polish over quantity.

**How to apply:**
- When scoping (e.g. the evaluation-engine build), keep the MVP tight: do the core comparison
  (single-LLM vs multi-agent vs one ablation, ~8 benchmark items) flawlessly before adding more
  conditions/items. Don't add breadth until the core is perfect.
- Proactively suggest trimming low-value or half-baked features rather than shipping them rough.
- "Done" means production-quality: verified end-to-end, handles errors, clean UI (see
  [[ui-must-be-hci-friendly]]), tested. Not "it runs."
- If a feature can't be made top-notch in the available time, cut it and say so — don't ship it weak.
