---
name: thesis-writing-plan
description: "Plan and template for writing the M.Sc thesis \"book\"; deferred until AFTER the project build is complete"
metadata: 
  node_type: memory
  type: project
  originSessionId: 002ae7a3-c3f4-4716-8731-9b15900f39c5
  modified: 2026-08-15T13:18:56.018Z
---

**Sequence (user decision, Aug 2026):** finish BUILDING the project (evaluation engine + experiments
dashboard — see the approved build plan) FIRST, then write the thesis book. Do not start thesis
writing until the build + real experiment results exist. Results/Evaluation/Conclusion chapters
need real data — never fabricate numbers.

**Format:** LaTeX. University template already downloaded and extracted to
`multi-agent-ai-test-framework/thesis/pmit-template/` (main file `thesis.tex`).
Source: PMIT Project Report Template from https://pmit.iitju.edu.bd/resource-library
(zip saved as `thesis/pmit-template.zip`).

**Template requirements (follow exactly):**
- Institution: IIT, Jahangirnagar University — PMIT (Professional Masters in Information Technology).
- `report` class, 12pt, one-sided, 1.5 spacing.
- Citations: IEEE style (`\bibliographystyle{ieeetr}`, numbered natbib) → `[1]`. Bib in `bibfile.bib`.
- Front matter order: Title page → Declaration → Certificate → Acknowledgements → Abstract →
  List of Abbreviations → List of Notations → LoF → LoT → ToC.
- Title-page macro `\titlepage{Title}{StudentID}{Degree}{Department}{Month Year}{Supervisor}`.
- 6 chapters via `\input{ChapN/ChapterN}`.

**Agreed 6-chapter mapping:**
1. Introduction (problem, motivation, RQs, contributions)
2. Background & Literature Review (incl. Related Work comparison — draft already exists at
   `thesis/related-work-positioning.md`)
3. Proposed Multi-Agent Framework (methodology / system design)
4. Implementation
5. Evaluation & Results (after experiments)
6. Conclusion & Future Work (after experiments)

**Draft RQs:** (1) Do collaborating agents generate requirement-driven test cases that catch more
seeded faults than a single-LLM baseline? (2) How much does the Reviewer<->Consensus debate
contribute (ablation)? (3) Does the gain hold across different LLMs?

**Draft contributions:** requirements-driven multi-agent framework; objective fault-based
(mutation) evaluation method; statistically-tested single-vs-multi-vs-ablation study (the closest
papers CANDOR/Nexus lack significance testing); open requirement->buggy-code benchmark; working
multi-provider tool.

**Related Work already grounded** (read the actual papers): see [[thesis-related-papers]] and
`thesis/related-work-positioning.md`. Honest novelty = the COMBINATION (requirements-driven +
statistically-tested controlled comparison), NOT "multi-agent" or "mutation testing" alone —
CANDOR already uses mutation score; Nexus already uses NL input. Neither reports significance tests.

**Title-page metadata STILL NEEDED from user before compiling:** full name(s) (possibly a
co-author — user said "our"), student ID(s), supervisor name+title, submission month/year,
final confirmed title (working title: "A Multi-Agent AI Framework for Automated Software Test
Case Generation and Validation from Software Requirements").
