# Related Work — Positioning & Precise Differences (working draft)

> Draft content (Markdown). Will be converted to LaTeX once the university template is provided.
> Every factual claim about a competing paper below was extracted by reading that paper's
> full text (arXiv). Citation numbers refer to the thesis reference list; verify final
> numbering when the .bib is assembled.

## 1. The research gap (motivation anchor)

The most authoritative survey of LLM-based software testing [Wang2024], covering 102
primary studies, finds that LLM applications cluster in the **middle-to-late** testing
lifecycle — chiefly *unit-test generation*, *test-oracle generation*, and *program
repair* — and reports verbatim that *"we do not find the practices for applying LLMs in
the tasks of early testing life-cycle (such as test requirement, test plan, etc.)."* The
same survey observes that for generated tests *"the coverage and the meaningfulness of the
generated tests are still far from satisfactory,"* and names *"rigorous evaluations"* an
open challenge. It gives no dedicated treatment of multi-agent / agent-collaboration
testing frameworks among the 102 studies.

**Two gaps follow directly:** (i) LLM test generation is overwhelmingly *code-driven and
function-level*, not *requirements-driven*; and (ii) evaluation rigor — controlled
comparison and fault-detection evidence with statistical backing — is lacking. This thesis
targets both.

## 2. Closest related work (multi-agent test/oracle generation)

**CANDOR** [Xu2025] — *Hallucination to Consensus: Multi-Agent LLMs for End-to-End JUnit
Test Generation.* ~9 agents (Initializer, Planner, Tester, Inspector, Requirement Engineer,
a 3-Panelist "panel discussion" with paired Interpreters, and a Curator that forms
**consensus** over the panelists' reasoning). Generates JUnit tests whose **prefixes derive
solely from source code**; natural-language descriptions are used only to *correct oracles*.
Evaluated on HumanEvalJava and LeetCodeJava with **line/branch coverage, mutation score
(PiTest), and oracle correctness**; includes an agent ablation. **No statistical
significance testing is reported.**

**Nexus** [Huang2025b] — *Execution-Grounded Multi-Agent Test Oracle Synthesis.* Four
critique specialists (Specification Expert, Edge-Case Specialist, Functional Validator,
Algorithmic Analyst) plus a tentative-oracle generator and Curator. Input is a
**natural-language function docstring + predefined test inputs** (no source code); oracles
are validated by executing them against an **LLM-synthesized** implementation in a sandbox,
then self-refined. Evaluated on seven code benchmarks with **oracle accuracy, bug-detection
rate, and Pass@1 repair**; includes phase- and agent-level ablations. **No statistical
significance testing is reported.**

## 3. Broader multi-agent LLM frameworks (adjacent)

**AgentCoder** [Huang2023] — three agents (Programmer, Test-designer, Test-executor) in an
iterative feedback loop. Input is a **HumanEval/MBPP-style coding prompt**; the goal is
correct **code**, with tests used only as a correctness oracle. Reports **Pass@1**; no
coverage, mutation, ablation, or significance analysis of the tests themselves.

**MetaGPT** [Hong2024] — five SOP-driven roles (Product Manager, Architect, Project
Manager, Engineer, **QA Engineer**) over a publish–subscribe message pool. Turns a one-line
requirement into a full program; the QA Engineer writes unit tests **as a subordinate step
to improve code**, not as the evaluated deliverable. Reports code-centric metrics (Pass@1,
executability, cost).

## 4. Comparison

| Aspect | CANDOR [Xu2025] | Nexus [Huang2025b] | AgentCoder [Huang2023] | MetaGPT [Hong2024] | **This thesis** |
|---|---|---|---|---|---|
| Primary input | Source code (+ NL to fix oracles) | NL function docstring + test inputs | Coding prompt (HumanEval-style) | One-line requirement | **NL software requirements / user stories** |
| Deliverable | JUnit tests + oracles | Test oracles/assertions | Correct code | Full program (code + docs + tests) | **Structured test-case suite (steps, expected result, type, traceability, priority)** |
| Granularity | Function/method | Function | Function | Project | **Requirement / acceptance-criterion** |
| Agent interaction | Panel discussion → Curator consensus | Deliberation → execution-grounded validation → refinement | Programmer↔executor feedback loop | SOP assembly line, pub/sub | **Bounded Reviewer↔Consensus debate (logged transcript) + LLM-planner Orchestrator w/ guardrails** |
| Test-quality evaluation | Coverage, mutation score, oracle correctness | Oracle accuracy, bug-detection rate | Pass@1 (code) | Pass@1, executability | **Mutation score / fault detection (reference-as-oracle differential testing)** |
| Controlled baseline comparison | vs EvoSuite, single-LLM, TOGLL | vs direct-gen, CANDOR | vs single-agent | vs single-agent | **Single-LLM vs full pipeline vs ablations** |
| Agent ablation | Yes | Yes | No | No | **Yes** |
| Statistical significance | **No** | **No** | No | No | **Yes (Wilcoxon signed-rank + effect size)** |

## 5. Precise differences (thesis-ready prose)

**vs. CANDOR.** CANDOR derives its test prefixes *solely from program source code* and uses
the natural-language description only to repair oracles [Xu2025]; this thesis instead takes
natural-language **requirements/user stories as the primary input** and generates a full
test-case suite with **no source-code seed**, operating at the requirement level rather than
the Java method level. Both use a consensus mechanism, but CANDOR's is a Curator over a fixed
panel discussion, whereas ours is a **bounded, transcript-logged Reviewer↔Consensus debate**
coordinated by an explicit LLM-planner Orchestrator. Critically, CANDOR reports no
statistical significance testing, whereas we validate every claimed improvement with a
**Wilcoxon signed-rank test and effect size**.

**vs. Nexus.** Like Nexus, we consume natural-language specifications rather than source
code, but Nexus operates at the level of a single function's **oracle synthesis**, grounding
correctness by executing oracles against an **LLM-synthesized** implementation [Huang2025b];
we instead generate **complete requirement-level test cases** and measure their
**fault-detection power via mutation scoring against a trusted reference implementation**
(differential testing). Nexus reports only point-estimate accuracy and bug-detection gains
with no significance testing; our evaluation is a **controlled single-LLM-vs-multi-agent-vs-
ablation comparison under Wilcoxon significance with effect sizes**.

**vs. AgentCoder / MetaGPT.** In both, test generation is *instrumental to producing correct
code* and is never evaluated as a first-class outcome — neither reports coverage, mutation,
ablation, or significance for the tests themselves [Huang2023, Hong2024]. This thesis makes
requirements-driven **test effectiveness the central, independently measured outcome**.

## 6. Honest novelty statement (defensible)

> Multi-agent LLM test generation is an active area, and objective evaluation (coverage,
> mutation, execution-grounding) already appears in the closest works. The contribution of
> this thesis is therefore **not** "using multiple agents" or "using mutation testing" in
> isolation, but the combination of: **(1)** a *requirements-driven* multi-agent pipeline
> that produces requirement-level test cases (addressing the early-lifecycle gap the survey
> [Wang2024] identifies as unaddressed); and **(2)** a *controlled, statistically-tested*
> comparison (single-LLM vs. full pipeline vs. agent ablations) that quantifies, with
> significance testing neither closest competitor provides, how much multi-agent
> collaboration improves fault detection.

### Placeholder citation keys (finalize in .bib)
Wang2024 (survey, IEEE TSE), Xu2025 (CANDOR), Huang2025b (Nexus), Huang2023 (AgentCoder),
Hong2024 (MetaGPT). Full verified links are in the project reading-list memory.
