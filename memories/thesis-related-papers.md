---
name: thesis-related-papers
description: "Verified reading list / bibliography for the M.Sc thesis on multi-agent AI test generation; use when writing Related Work, Methodology, or Evaluation chapters"
metadata: 
  node_type: memory
  type: reference
  originSessionId: 002ae7a3-c3f4-4716-8731-9b15900f39c5
  modified: 2026-08-15T13:00:54.217Z
---

Verified (links confirmed via web search Aug 2026) curated bibliography for the M.Sc thesis
"A Multi-Agent AI Framework for Automated Software Test Case Generation and Validation from
Software Requirements." Use these when writing the thesis "book". Related: [[thesis-primary-outputs]], [[agentic-orchestrator]].

**Closest related work — position the thesis against these first:**
- CANDOR — Multi-Agent LLMs for End-to-End JUnit Test Generation (Xu et al., 2025) — https://arxiv.org/abs/2506.02943
- Nexus — Execution-Grounded Multi-Agent Test Oracle Synthesis (Huang et al., 2025) — https://arxiv.org/abs/2510.26423
Our differentiation vs these: requirements-driven input + mutation-based fault proof + ablation quantifying each agent's marginal contribution.

**Surveys (anchor Related Work):**
- Software Testing with LLMs: Survey, Landscape, Vision — Wang et al., IEEE TSE 2024 — https://arxiv.org/abs/2307.07221 (central reference)
- LLMs for SE: A Systematic Literature Review — Hou et al., ACM TOSEM 2024 — https://arxiv.org/abs/2308.10620
- LLMs for SE: Survey and Open Problems — Fan et al., ICSE-FoSE 2023 — https://arxiv.org/abs/2310.03533
- LLMs for Unit Test Generation: Achievements/Challenges/Opportunities — Chu et al., 2025 — https://arxiv.org/abs/2511.21382

**LLM test generation (baseline context):**
- TestPilot — Schäfer et al., IEEE TSE 2023 — https://arxiv.org/abs/2302.06527
- ChatTester (No More Manual Tests?) — Yuan et al., 2023 — https://arxiv.org/abs/2305.04207
- CodaMOSA — Lemieux et al., ICSE 2023 — https://www.carolemieux.com/codamosa_icse23.pdf
- ChatUniTest — Chen et al., FSE 2024 — https://arxiv.org/abs/2305.04764

**Multi-agent collaboration (core contribution grounding):**
- MetaGPT — Hong et al., ICLR 2024 — https://arxiv.org/abs/2308.00352
- AgentCoder — Huang et al., 2023 — https://arxiv.org/abs/2312.13010
- ChatDev — Qian et al., ACL 2024 — https://arxiv.org/abs/2307.07924
- AutoGen — Wu et al., 2023 — https://arxiv.org/abs/2308.08155
- Multiagent Debate — Du et al., ICML 2024 — https://arxiv.org/abs/2305.14325 (justifies the Reviewer<->Consensus debate)
- CAMEL — Li et al., NeurIPS 2023 — https://arxiv.org/abs/2303.17760

**Agent reasoning foundations:**
- ReAct — Yao et al., ICLR 2023 — https://arxiv.org/abs/2210.03629
- Reflexion — Shinn et al., NeurIPS 2023 — https://arxiv.org/abs/2303.11366
- Chain-of-Thought — Wei et al., NeurIPS 2022 — https://arxiv.org/abs/2201.11903

**Mutation testing — justifies the fault-based evaluation (the thesis's unique angle):**
- Are Mutants a Valid Substitute for Real Faults? — Just et al., FSE 2014 — https://homes.cs.washington.edu/~rjust/publ/mutants_real_faults_fse_2014.pdf (methodology justification)
- Analysis & Survey of Mutation Testing — Jia & Harman, IEEE TSE 2011 — https://doi.org/10.1109/TSE.2010.62
- Mutation Testing Advances: A Survey — Papadakis et al., 2019 — https://mutationtesting.uni.lu/survey.pdf
- Defects4J — Just et al., ISSTA 2014 — https://homes.cs.washington.edu/~rjust/publ/defects4j_issta_2014.pdf
- EvoSuite — Fraser & Arcuri, ESEC/FSE 2011 — https://www.evosuite.org/wp-content/papercite-data/pdf/esecfse11.pdf

Other 2025 preprints: HPCAgentTester (https://arxiv.org/abs/2511.10860), AgoneTest (https://arxiv.org/abs/2511.20403).
2025 items are arXiv preprints — cite as preprints. Verify title/venue on Google Scholar before final citation.
