import { Fragment, useEffect, useMemo, useState } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { api, getModelSelection, setModelSelection } from "../api/client";
import { REQ_TYPE_LABEL } from "./constants";
import UsagePanel from "../components/UsagePanel";

const PROVIDER_LABEL = {
  gemini: "Google Gemini",
  groq: "Groq",
  openrouter: "OpenRouter",
  anthropic: "Anthropic",
  ollama: "Ollama",
};

// Dropdown to choose which free model powers every agent action on this page.
// Selection persists in localStorage (via the api client) and is attached to
// each generate/run/orchestrate call, so switching models needs no file edits.
function ModelPicker() {
  const [catalog, setCatalog] = useState(null);
  const [sel, setSel] = useState(getModelSelection());

  useEffect(() => {
    api
      .listModels()
      .then((data) => {
        setCatalog(data);
        if (!getModelSelection()) {
          const d = data.default;
          const match = data.models.find(
            (m) => m.provider === d.provider && m.model === d.model && m.ready
          );
          const first = match || data.models.find((m) => m.ready);
          if (first) {
            setModelSelection(first);
            setSel({ provider: first.provider, model: first.model });
          }
        }
      })
      .catch(() => {});
  }, []);

  if (!catalog) return null;

  const current = sel || catalog.default;
  const value = `${current.provider}::${current.model}`;
  const groups = {};
  for (const m of catalog.models) (groups[m.provider] ||= []).push(m);

  function onChange(e) {
    const [provider, model] = e.target.value.split("::");
    setModelSelection({ provider, model });
    setSel({ provider, model });
  }

  return (
    <label className="model-picker" title="Which AI model runs every agent on this page">
      <span className="mp-label">AI model</span>
      <select value={value} onChange={onChange}>
        {Object.entries(groups).map(([prov, items]) => (
          <optgroup key={prov} label={PROVIDER_LABEL[prov] || prov}>
            {items.map((m) => (
              <option
                key={`${m.provider}::${m.model}`}
                value={`${m.provider}::${m.model}`}
                disabled={!m.ready}
              >
                {m.label}
                {m.ready ? "" : " — add key"}
              </option>
            ))}
          </optgroup>
        ))}
      </select>
    </label>
  );
}

const PIPELINE_STEPS = ["Analyze", "Generate", "Review", "Coverage", "Quality"];
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

// Spinner + label shown on any agent button while it is working.
function Busy({ children }) {
  return (
    <span className="busy-label">
      <span className="spinner" />
      {children}
    </span>
  );
}

const AGENT_LABEL = {
  analyze: "Analyst",
  generate: "Generator",
  debate: "Reviewer ⇄ Consensus",
  coverage: "Validator",
  quality: "Quality",
  prioritize: "Prioritizer",
  finish: "Done — goal met",
};

// The orchestrator's decision trace: which agent it dispatched each step and why.
function OrchestrationTrace({ data }) {
  const qpct = Math.round((data.quality_score || 0) * 100);
  return (
    <div className="orch">
      <div className="debate-summary">
        <span className="chip chip-accent">{data.steps_used} decisions</span>
        <span className={`chip ${data.coverage_pct === 100 ? "chip-green" : "chip-amber"}`}>
          {data.coverage_pct}% coverage
        </span>
        <span className="chip chip-grey">{qpct}% quality</span>
        <span className="chip chip-grey">{data.test_case_count} test cases</span>
      </div>
      <ol className="orch-timeline">
        {(data.decisions || []).map((d) => (
          <li key={d.step} className="orch-step">
            <span className="orch-num">{d.step}</span>
            <div style={{ minWidth: 0 }}>
              <div className="orch-agent">
                {AGENT_LABEL[d.action] || d.action}
                {d.planner_fallback && (
                  <span className="chip chip-amber" style={{ marginLeft: 8 }}>
                    guardrail
                  </span>
                )}
              </div>
              <div className="orch-why">{d.rationale}</div>
            </div>
          </li>
        ))}
      </ol>
    </div>
  );
}

export const REQ_TABS = [
  { key: "overview", label: "Overview" },
  { key: "test", label: "Test Cases" },
  { key: "review", label: "Review" },
  { key: "coverage", label: "Coverage" },
  { key: "quality", label: "Quality" },
  { key: "export", label: "Export" },
];

export default function RequirementDetail() {
  const { projectId, requirementId } = useParams();
  const [searchParams, setSearchParams] = useSearchParams();
  const activeTab = searchParams.get("tab") || "overview";
  function setTab(t) {
    setSearchParams(t === "overview" ? {} : { tab: t }, { replace: true });
  }
  const [story, setStory] = useState(null);
  const [result, setResult] = useState(null);
  const [generation, setGeneration] = useState(null);
  const [debate, setDebate] = useState(null);
  const [coverage, setCoverage] = useState(null);
  const [quality, setQuality] = useState(null);
  const [baseline, setBaseline] = useState(null);
  const [mode, setMode] = useState("multi"); // "multi" | "baseline"
  const [inputMode, setInputMode] = useState("requirement"); // "requirement" | "criteria"
  const [acText, setAcText] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [running, setRunning] = useState(false);
  const [submittingAc, setSubmittingAc] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [reviewing, setReviewing] = useState(false);
  const [prioritizing, setPrioritizing] = useState(false);
  const [analysingCoverage, setAnalysingCoverage] = useState(false);
  const [evaluatingQuality, setEvaluatingQuality] = useState(false);
  const [baselining, setBaselining] = useState(false);
  const [exporting, setExporting] = useState("");
  const [runningAll, setRunningAll] = useState(false);
  const [pipelineIdx, setPipelineIdx] = useState(-1);
  const [plSteps, setPlSteps] = useState(PIPELINE_STEPS);
  const [orchestrating, setOrchestrating] = useState(false);
  const [orchestration, setOrchestration] = useState(null);

  // Floor each agent action to a short minimum so its loading state is
  // actually visible (a no-op once a real LLM call takes longer).
  const pace = (p) => Promise.all([p, sleep(500)]).then(([r]) => r);

  useEffect(() => {
    setLoading(true);
    Promise.all([
      api.getRequirement(projectId, requirementId),
      api.getLatestAnalysis(projectId, requirementId).catch(() => null),
      api.getLatestTestCases(projectId, requirementId).catch(() => null),
      api.getLatestReviewConsensus(projectId, requirementId).catch(() => null),
      api.getLatestCoverage(projectId, requirementId).catch(() => null),
      api.getLatestQuality(projectId, requirementId).catch(() => null),
      api.getLatestBaseline(projectId, requirementId).catch(() => null),
    ])
      .then(([s, r, g, d, cov, q, b]) => {
        setStory(s);
        setResult(r);
        setGeneration(g);
        setDebate(d);
        setCoverage(cov);
        setQuality(q);
        setBaseline(b);
        // Reflect how the latest run was seeded: criteria supplied directly
        // (no analysis) vs derived from the requirement.
        if (r && !r.analysis && r.acceptance_criteria?.length) {
          setInputMode("criteria");
        }
      })
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, [projectId, requirementId]);

  async function onAnalyze() {
    setRunning(true);
    setError("");
    try {
      setResult(await pace(api.runRequirementAnalysis(projectId, requirementId)));
    } catch (err) {
      setError(err.message);
    } finally {
      setRunning(false);
    }
  }

  async function onSubmitCriteria() {
    const criteria = acText
      .split("\n")
      .map((line) => line.trim())
      .filter(Boolean);
    if (criteria.length === 0) return;
    setSubmittingAc(true);
    setError("");
    try {
      // A fresh criteria set means any previously generated cases / debate are
      // stale — clear them so the UI reflects the new run.
      setResult(await pace(api.submitAcceptanceCriteria(projectId, requirementId, criteria)));
      setGeneration(null);
      setDebate(null);
    } catch (err) {
      setError(err.message);
    } finally {
      setSubmittingAc(false);
    }
  }

  async function onGenerate() {
    setGenerating(true);
    setError("");
    try {
      setGeneration(await pace(api.generateTestCases(projectId, requirementId)));
      setDebate(null); // stale once test cases change
      setCoverage(null);
      setQuality(null);
    } catch (err) {
      setError(err.message);
    } finally {
      setGenerating(false);
    }
  }

  async function onReviewConsensus() {
    setReviewing(true);
    setError("");
    try {
      const d = await pace(api.runReviewConsensus(projectId, requirementId));
      setDebate(d);
      // consensus can add/revise cases — refresh the multi-agent set
      setGeneration(await api.getLatestTestCases(projectId, requirementId));
      setCoverage(null); // coverage recomputed against the revised suite
      setQuality(null);
    } catch (err) {
      setError(err.message);
    } finally {
      setReviewing(false);
    }
  }

  async function onPrioritize() {
    setPrioritizing(true);
    setError("");
    try {
      setGeneration(await pace(api.prioritize(projectId, requirementId)));
    } catch (err) {
      setError(err.message);
    } finally {
      setPrioritizing(false);
    }
  }

  async function onCoverage() {
    setAnalysingCoverage(true);
    setError("");
    try {
      setCoverage(await pace(api.runCoverage(projectId, requirementId)));
    } catch (err) {
      setError(err.message);
    } finally {
      setAnalysingCoverage(false);
    }
  }

  async function onQuality() {
    setEvaluatingQuality(true);
    setError("");
    try {
      setQuality(await pace(api.runQuality(projectId, requirementId)));
    } catch (err) {
      setError(err.message);
    } finally {
      setEvaluatingQuality(false);
    }
  }

  async function onBaseline() {
    setBaselining(true);
    setError("");
    try {
      setBaseline(await pace(api.runBaseline(projectId, requirementId)));
    } catch (err) {
      setError(err.message);
    } finally {
      setBaselining(false);
    }
  }

  // One-click: run the whole multi-agent pipeline end to end.
  async function onRunAll() {
    setError("");
    setRunningAll(true);
    setMode("multi");
    // Each agent call is paced to a minimum visible duration so the progress
    // bar actually reads as "the AI is working" even on the instant mock
    // provider. With a real LLM the call dominates and this floor is a no-op.
    const MIN = 700;
    const paced = async (promise) => {
      const [res] = await Promise.all([promise, sleep(MIN)]);
      return res;
    };
    // Number the steps by what actually runs this time: if acceptance criteria
    // already exist, the analysis step is skipped, so it isn't counted.
    const willAnalyze = criteria.length === 0;
    const steps = willAnalyze ? PIPELINE_STEPS : PIPELINE_STEPS.slice(1);
    setPlSteps(steps);
    let i = 0;
    try {
      let crit = criteria;
      if (willAnalyze) {
        setPipelineIdx(i);
        if (inputMode === "criteria") {
          const lines = acText
            .split("\n")
            .map((l) => l.trim())
            .filter(Boolean);
          if (lines.length === 0)
            throw new Error(
              "Add acceptance criteria (one per line), or switch Input to “From Requirement”."
            );
          const res = await paced(
            api.submitAcceptanceCriteria(projectId, requirementId, lines)
          );
          setResult(res);
          crit = res?.acceptance_criteria || [];
        } else {
          const res = await paced(api.runRequirementAnalysis(projectId, requirementId));
          setResult(res);
          crit = res?.acceptance_criteria || [];
        }
        i++;
      }
      if (crit.length === 0)
        throw new Error("No acceptance criteria were produced — nothing to generate from.");

      // Generate.
      setPipelineIdx(i++);
      setGeneration(await paced(api.generateTestCases(projectId, requirementId)));

      // Review & consensus (may revise the suite).
      setPipelineIdx(i++);
      setDebate(await paced(api.runReviewConsensus(projectId, requirementId)));
      setGeneration(await api.getLatestTestCases(projectId, requirementId));

      // Coverage.
      setPipelineIdx(i++);
      setCoverage(await paced(api.runCoverage(projectId, requirementId)));

      // Quality.
      setPipelineIdx(i++);
      setQuality(await paced(api.runQuality(projectId, requirementId)));

      // Let the bar reach 100% and settle before clearing.
      setPipelineIdx(steps.length);
      await sleep(500);
    } catch (err) {
      setError(err.message);
    } finally {
      setRunningAll(false);
      setPipelineIdx(-1);
    }
  }

  // Autonomous agentic run: the Orchestrator's planner drives the specialists.
  async function onOrchestrate() {
    setOrchestrating(true);
    setError("");
    setMode("multi");
    try {
      const res = await api.orchestrate(projectId, requirementId);
      setOrchestration(res);
      // Refresh every artifact so all tabs reflect the agentic run.
      const [r, g, d, cov, q] = await Promise.all([
        api.getLatestAnalysis(projectId, requirementId).catch(() => null),
        api.getLatestTestCases(projectId, requirementId).catch(() => null),
        api.getLatestReviewConsensus(projectId, requirementId).catch(() => null),
        api.getLatestCoverage(projectId, requirementId).catch(() => null),
        api.getLatestQuality(projectId, requirementId).catch(() => null),
      ]);
      setResult(r);
      setGeneration(g);
      setDebate(d);
      setCoverage(cov);
      setQuality(q);
    } catch (err) {
      setError(err.message);
    } finally {
      setOrchestrating(false);
    }
  }

  async function onExport(fmt) {
    setExporting(fmt);
    setError("");
    try {
      await api.exportPackage(projectId, requirementId, fmt);
    } catch (err) {
      setError(err.message);
    } finally {
      setExporting("");
    }
  }

  if (loading)
    return (
      <div className="content">
        <p className="muted">Loading…</p>
      </div>
    );
  if (error && !story)
    return (
      <div className="content">
        <p className="error">{error}</p>
      </div>
    );

  const analysis = result?.analysis;
  const criteria = result?.acceptance_criteria || [];
  const multiCases = generation?.test_cases || [];
  const baselineCases = baseline?.test_cases || [];

  return (
    <div className="content">
      <div className="page">
        <p className="crumb">
          <Link to="/">Home</Link>
          <span className="sep">/</span>
          <Link to={`/projects/${projectId}`}>Project</Link>
          <span className="sep">/</span>
          <span>{story?.title}</span>
        </p>
        <header className="page-head">
          <div>
            <h1>{story?.title}</h1>
            {story && (
              <div className="case-badges" style={{ marginTop: 10 }}>
                <span className="chip chip-accent">{REQ_TYPE_LABEL[story.req_type] || story.req_type}</span>
                <span className="chip chip-grey">priority: {story.priority}</span>
                <span className="chip chip-grey">status: {story.status}</span>
                {story.source_filename && (
                  <span className="chip chip-grey">📎 {story.source_filename}</span>
                )}
              </div>
            )}
          </div>
          <ModelPicker />
        </header>

        <div className="tabbar">
          {REQ_TABS.map((t) => (
            <button
              key={t.key}
              className={activeTab === t.key ? "active" : ""}
              onClick={() => setTab(t.key)}
            >
              {t.label}
            </button>
          ))}
        </div>

        {error && <p className="error" style={{ margin: "0 0 4px" }}>{error}</p>}

        {activeTab === "overview" && (
          <>
        <section className="section">
          <h2>Requirement</h2>
          <p className="story-text">{story?.raw_text}</p>
        </section>

        <UsagePanel />

        <section className="runall-bar">
          <div className="txt">
            <h3>Generate the full test design in one go</h3>
            <p>
              Runs the whole multi-agent pipeline — analysis → generation →
              review &amp; consensus → coverage → quality — end to end. You can
              still run any stage individually below.
            </p>
          </div>
          <button className="btn-primary" onClick={onRunAll} disabled={runningAll}>
            {runningAll ? (
              <>
                <span className="spinner" /> Working…
              </>
            ) : generation ? (
              "Re-run full pipeline"
            ) : (
              "Run full pipeline"
            )}
          </button>
          {runningAll &&
            (() => {
              const total = plSteps.length;
              const done = Math.min(pipelineIdx, total);
              const pct = Math.round((Math.min(pipelineIdx + 1, total) / total) * 100);
              const current = plSteps[pipelineIdx];
              return (
                <div className="pl-progress">
                  <div className="pl-head">
                    <span className="step">
                      {current
                        ? `Step ${done + 1} of ${total} · ${current}`
                        : "Finishing up"}
                    </span>
                    <span className="pct">{pct}%</span>
                  </div>
                  <div className="pl-track">
                    <div className="pl-fill" style={{ width: `${pct}%` }} />
                  </div>
                  <div className="pipeline-progress">
                    {plSteps.map((s, i) => (
                      <div
                        key={s}
                        className={`pp-step ${
                          i < pipelineIdx ? "done" : i === pipelineIdx ? "active" : ""
                        }`}
                      >
                        <span className="pp-dot" /> {s}
                      </div>
                    ))}
                  </div>
                </div>
              );
            })()}
        </section>

        <section className="section orch-card">
          <div className="section-head">
            <h2>Autonomous agent · Orchestrator</h2>
            <button className="btn-primary" onClick={onOrchestrate} disabled={orchestrating || runningAll}>
              {orchestrating ? <Busy>Orchestrating…</Busy> : "Run agentic orchestrator"}
            </button>
          </div>
          <p className="mode-note">
            Unlike “Run full pipeline” (a fixed sequence), the Orchestrator’s
            planner <strong>decides which agent to run next</strong> from the
            live state, under guardrails — and logs every decision. This is the
            framework’s agentic control loop.
          </p>
          {orchestration && <OrchestrationTrace data={orchestration} />}
        </section>

        <section className="section">
          <div className="section-head">
            <h2>Input</h2>
            <div className="mode-toggle" role="tablist">
              <button
                className={`mode-btn ${inputMode === "requirement" ? "active" : ""}`}
                onClick={() => setInputMode("requirement")}
              >
                From Requirement
              </button>
              <button
                className={`mode-btn ${inputMode === "criteria" ? "active" : ""}`}
                onClick={() => setInputMode("criteria")}
              >
                From Acceptance Criteria
              </button>
            </div>
          </div>

          {inputMode === "requirement" ? (
            <>
              <p className="muted mode-note">
                The Analyzer breaks the user story above into a structured,
                testable specification and derives acceptance criteria.
              </p>
              <div className="inline-actions">
                <button onClick={onAnalyze} disabled={running || runningAll}>
                  {running ? (
                    <Busy>Analyzing…</Busy>
                  ) : analysis ? (
                    "Re-run analysis"
                  ) : (
                    "Run analysis"
                  )}
                </button>
              </div>
            </>
          ) : (
            <>
              <p className="muted mode-note">
                Paste acceptance criteria directly — one per line. Test generation
                and the debate run straight from these, skipping analysis.
              </p>
              <textarea
                className="ac-input"
                rows={6}
                placeholder={"User can log in with valid credentials\nInvalid credentials are rejected with an error\nAccount locks after 5 failed attempts"}
                value={acText}
                onChange={(e) => setAcText(e.target.value)}
              />
              <div className="inline-actions">
                <button onClick={onSubmitCriteria} disabled={submittingAc || !acText.trim()}>
                  {submittingAc ? <Busy>Saving…</Busy> : "Use these criteria"}
                </button>
              </div>
            </>
          )}

          {result?.error && <p className="error">{result.error}</p>}

          {analysis && (
            <div className="analysis">
              <AnalysisList title="Actors" items={analysis.actors} />
              <AnalysisList title="Preconditions" items={analysis.preconditions} />
              <AnalysisList title="Main flow" items={analysis.main_flow} ordered />
              <AnalysisList title="Alternative flows" items={analysis.alt_flows} />
              <div className="analysis-block">
                <h3>Acceptance criteria</h3>
                {criteria.length === 0 ? (
                  <p className="muted">None extracted.</p>
                ) : (
                  <ul>
                    {criteria.map((c) => (
                      <li key={c.id}>
                        <code>AC{c.order + 1}</code> {c.text}
                      </li>
                    ))}
                  </ul>
                )}
              </div>
              <AnalysisList title="Ambiguities" items={analysis.ambiguities} />
            </div>
          )}

          {/* AC-direct: no analysis object, but criteria exist — show them. */}
          {!analysis && criteria.length > 0 && (
            <div className="analysis">
              <div className="analysis-block">
                <h3>Acceptance criteria (supplied)</h3>
                <ul>
                  {criteria.map((c) => (
                    <li key={c.id}>
                      <code>AC{c.order + 1}</code> {c.text}
                    </li>
                  ))}
                </ul>
              </div>
            </div>
          )}
        </section>

          </>
        )}

        {activeTab === "test" && (
          <>
        {/* Mode toggle: the two research arms compared side by side. */}
        <section className="section">
          <div className="section-head">
            <h2>Test generation</h2>
            <div className="mode-toggle" role="tablist">
              <button
                className={`mode-btn ${mode === "multi" ? "active" : ""}`}
                onClick={() => setMode("multi")}
              >
                Multi-agent
              </button>
              <button
                className={`mode-btn ${mode === "baseline" ? "active" : ""}`}
                onClick={() => setMode("baseline")}
              >
                Single-LLM baseline
              </button>
            </div>
          </div>

          {mode === "multi" ? (
            <>
              <p className="muted mode-note">
                Requirement Analysis → Test Generation → the Reviewer ⇄ Consensus
                debate. Test cases are traced to acceptance criteria and revised
                collaboratively.
              </p>
              <div className="inline-actions">
                <button onClick={onGenerate} disabled={criteria.length === 0 || generating || runningAll}>
                  {generating ? <Busy>Generating…</Busy> : "Generate test cases"}
                </button>
              </div>
              {multiCases.length === 0 ? (
                <p className="muted">
                  Provide acceptance criteria (analyse a requirement or paste them
                  directly), then generate a full, traceable test suite.
                </p>
              ) : (
                <TestCaseTable cases={multiCases} showTrace />
              )}
            </>
          ) : (
            <>
              <p className="muted mode-note">
                The control arm: one LLM call turns the story straight into test
                cases — no analysis, no reviewer, no consensus. Its cases carry no
                acceptance-criterion traceability, which is exactly what the
                multi-agent pipeline is measured against.
              </p>
              <div className="inline-actions">
                <button onClick={onBaseline} disabled={baselining}>
                  {baselining ? <Busy>Running…</Busy> : "Run single-LLM baseline"}
                </button>
              </div>
              {baselineCases.length === 0 ? (
                <p className="muted">
                  Run the baseline to generate test cases from the story in one step.
                </p>
              ) : (
                <TestCaseTable cases={baselineCases} />
              )}
            </>
          )}
        </section>

          </>
        )}

        {activeTab === "review" && (
          <section className="section">
            <div className="section-head">
              <h2>Review &amp; Consensus — multi-agent debate</h2>
              <button
                onClick={onReviewConsensus}
                disabled={multiCases.length === 0 || reviewing || runningAll}
              >
                {reviewing ? (
                  <Busy>Debating…</Busy>
                ) : debate ? (
                  "Re-run debate"
                ) : (
                  "Run review & consensus"
                )}
              </button>
            </div>
            <p className="muted mode-note">
              The Reviewer critiques the test cases; the Consensus agent rebuts,
              revises, or adds. They iterate in bounded rounds until the Reviewer
              is satisfied. This exchange is the collaborative core of the framework.
            </p>
            {debate?.error && <p className="error">{debate.error}</p>}
            {!debate ? (
              <p className="muted">
                Generate test cases first, then run the debate to see the agents
                critique and revise them.
              </p>
            ) : (
              <DebateTranscript debate={debate} />
            )}
          </section>
        )}

        {activeTab === "test" && (
          <section className="section">
            <div className="section-head">
              <h2>Prioritization</h2>
              <button onClick={onPrioritize} disabled={multiCases.length === 0 || prioritizing}>
                {prioritizing ? <Busy>Prioritizing…</Busy> : "Prioritize suite"}
              </button>
            </div>
            <p className="muted mode-note">
              The Prioritizer agent ranks the whole suite by business importance
              and assigns a production-impact severity — so a team under time
              pressure knows what to run first. Cases below are ordered by rank.
            </p>
            {multiCases.some((tc) => tc.rank != null) ? (
              <p className="muted">
                Ranked {multiCases.filter((tc) => tc.rank != null).length} case(s).
                Highest-priority cases appear first in the suite above.
              </p>
            ) : (
              <p className="muted">
                Generate (and optionally debate) test cases, then prioritize to
                rank and assign severity.
              </p>
            )}
          </section>
        )}

        {activeTab === "coverage" && (
          <section className="section">
            <div className="section-head">
              <h2>Coverage &amp; Validation</h2>
              <button onClick={onCoverage} disabled={multiCases.length === 0 || analysingCoverage || runningAll}>
                {analysingCoverage ? (
                  <Busy>Analysing…</Busy>
                ) : coverage ? (
                  "Re-run coverage"
                ) : (
                  "Analyse coverage"
                )}
              </button>
            </div>
            <p className="muted mode-note">
              The Validator builds a traceability matrix — which acceptance
              criterion is verified by which test case — and judges whether each
              is adequately covered or only superficially. Gaps are the untested
              requirements.
            </p>
            {coverage?.error && <p className="error">{coverage.error}</p>}
            {!coverage ? (
              <p className="muted">
                Generate test cases, then analyse coverage to see the
                requirement-to-test traceability matrix and any gaps.
              </p>
            ) : (
              <CoverageMatrix coverage={coverage} />
            )}
          </section>
        )}

        {activeTab === "quality" && (
          <section className="section">
            <div className="section-head">
              <h2>Quality Report</h2>
              <button onClick={onQuality} disabled={multiCases.length === 0 || evaluatingQuality || runningAll}>
                {evaluatingQuality ? (
                  <Busy>Evaluating…</Busy>
                ) : quality ? (
                  "Re-run quality"
                ) : (
                  "Evaluate quality"
                )}
              </button>
            </div>
            <p className="muted mode-note">
              The Quality agent scores every test case on clarity, atomicity, and
              traceability, and flags duplicates — the thesis's Quality Report and
              the final evaluated output of the pipeline.
            </p>
            {quality?.error && <p className="error">{quality.error}</p>}
            {!quality ? (
              <p className="muted">
                Generate test cases, then evaluate quality to score the suite and
                detect duplicates.
              </p>
            ) : (
              <QualityMatrix quality={quality} />
            )}
          </section>
        )}

        {activeTab === "export" && (
        <section className="section">
          <h2>Export test design package</h2>
          <p className="mode-note">
            Download the complete package — requirement, acceptance criteria,
            test cases with quality scores, and the coverage matrix — for the
            latest multi-agent run.
          </p>
          {multiCases.length === 0 ? (
            <p className="muted">
              Generate a multi-agent test suite first, then export it in any format.
            </p>
          ) : (
            <div className="export-bar">
              <span className="lbl">Download as</span>
              {EXPORT_FORMATS.map((f) => (
                <button
                  key={f.fmt}
                  className="export-btn"
                  onClick={() => onExport(f.fmt)}
                  disabled={exporting !== ""}
                >
                  {exporting === f.fmt ? "Preparing…" : f.label}
                </button>
              ))}
            </div>
          )}
        </section>
        )}
      </div>
    </div>
  );
}

const EXPORT_FORMATS = [
  { fmt: "json", label: "JSON" },
  { fmt: "csv", label: "CSV" },
  { fmt: "md", label: "Markdown" },
  { fmt: "xlsx", label: "Excel" },
  { fmt: "pdf", label: "PDF" },
];

const TYPE_CHIP = {
  functional: "chip-green",
  negative: "chip-red",
  boundary: "chip-amber",
  edge: "chip-amber",
  security: "chip-purple",
  api: "chip-accent",
  performance: "chip-grey",
};
const PRIORITY_CHIP = { high: "chip-red", medium: "chip-amber", low: "chip-grey" };
const SEV_CHIP = { critical: "chip-red", major: "chip-amber", minor: "chip-grey" };

// Group the grid by type in a sensible order (happy path first).
const TYPE_ORDER = {
  functional: 0,
  positive: 1,
  negative: 2,
  boundary: 3,
  edge: 4,
  security: 5,
  api: 6,
  performance: 7,
  usability: 8,
  integration: 9,
};
function typeRank(t) {
  return t in TYPE_ORDER ? TYPE_ORDER[t] : 50;
}

// The Type column already shows functional/negative/…; drop a redundant
// "<type>:" prefix from the title so it isn't repeated on every row.
function cleanTitle(tc) {
  let t = (tc.title || "").trim();
  t = t.replace(
    /^\s*(functional|negative|boundary|edge|security|api|performance|positive|usability|integration)\s*:\s*/i,
    ""
  );
  if (t) t = t.charAt(0).toUpperCase() + t.slice(1);
  return t;
}

function hasTestData(tc) {
  return (
    tc.test_data &&
    (Array.isArray(tc.test_data)
      ? tc.test_data.length > 0
      : Object.keys(tc.test_data).length > 0)
  );
}

function TestCaseTable({ cases, showTrace }) {
  const [filter, setFilter] = useState("all");
  const [expanded, setExpanded] = useState(() => new Set());

  const typeCounts = useMemo(() => {
    const counts = {};
    for (const tc of cases) {
      const t = tc.type || "other";
      counts[t] = (counts[t] || 0) + 1;
    }
    return counts;
  }, [cases]);

  const base =
    filter === "all"
      ? cases
      : cases.filter((tc) => (tc.type || "other") === filter);
  const filtered = [...base].sort((a, b) => {
    const ta = typeRank(a.type);
    const tb = typeRank(b.type);
    if (ta !== tb) return ta - tb;
    if ((a.type || "") !== (b.type || "")) return (a.type || "").localeCompare(b.type || "");
    const ra = a.rank != null ? a.rank : Infinity;
    const rb = b.rank != null ? b.rank : Infinity;
    if (ra !== rb) return ra - rb;
    return a.id - b.id;
  });

  function toggle(id) {
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  const colCount = showTrace ? 7 : 6;

  return (
    <div className="tc-panel">
      <div className="tc-tabs">
        <button
          className={filter === "all" ? "active" : ""}
          onClick={() => setFilter("all")}
        >
          All <span className="n">{cases.length}</span>
        </button>
        {Object.keys(typeCounts)
          .sort()
          .map((t) => (
            <button
              key={t}
              className={filter === t ? "active" : ""}
              onClick={() => setFilter(t)}
            >
              {t} <span className="n">{typeCounts[t]}</span>
            </button>
          ))}
      </div>

      <div className="tc-tablewrap">
        <table className="tc-table">
          <thead>
            <tr>
              <th className="c-ex" aria-label="expand" />
              <th className="c-num">#</th>
              <th>Type</th>
              <th>Test case</th>
              {showTrace && <th>Traces</th>}
              <th>Priority</th>
              <th>Severity</th>
            </tr>
          </thead>
          <tbody>
            {filtered.length === 0 ? (
              <tr>
                <td className="tc-empty" colSpan={colCount}>
                  No {filter} test cases.
                </td>
              </tr>
            ) : (
              filtered.map((tc, i) => {
                const open = expanded.has(tc.id);
                return (
                  <Fragment key={tc.id}>
                    <tr
                      className={`tc-row ${i % 2 ? "alt" : ""} ${open ? "open" : ""}`}
                      onClick={() => toggle(tc.id)}
                    >
                      <td className="c-ex">
                        <span className={`caret ${open ? "down" : ""}`}>▸</span>
                      </td>
                      <td className="c-num">{tc.rank != null ? tc.rank : i + 1}</td>
                      <td>
                        <span className={`chip ${TYPE_CHIP[tc.type] || "chip-grey"}`}>
                          {tc.type || "—"}
                        </span>
                      </td>
                      <td className="c-title">
                        {cleanTitle(tc)}
                        {tc.generated_by === "consensus" && (
                          <span className="chip chip-green tc-mini">
                            consensus v{tc.version}
                          </span>
                        )}
                        {tc.status === "reviewer_flagged" && (
                          <span className="chip chip-red tc-mini">flagged</span>
                        )}
                      </td>
                      {showTrace && (
                        <td>
                          {tc.traces_to ? (
                            <span className="chip chip-accent">AC #{tc.traces_to}</span>
                          ) : (
                            <span className="muted">—</span>
                          )}
                        </td>
                      )}
                      <td>
                        <span className={`chip ${PRIORITY_CHIP[tc.priority] || "chip-grey"}`}>
                          {tc.priority}
                        </span>
                      </td>
                      <td>
                        {tc.severity ? (
                          <span className={`chip ${SEV_CHIP[tc.severity] || "chip-grey"}`}>
                            {tc.severity}
                          </span>
                        ) : (
                          <span className="muted">—</span>
                        )}
                      </td>
                    </tr>
                    {open && (
                      <tr className="tc-detail">
                        <td colSpan={colCount}>
                          <div className="tc-detail-grid">
                            <div>
                              <div className="tc-lbl">Steps</div>
                              <ol>
                                {tc.steps?.map((step, idx) => (
                                  <li key={idx}>{step}</li>
                                ))}
                              </ol>
                            </div>
                            <div>
                              <div className="tc-lbl">Expected result</div>
                              <p>{tc.expected_result}</p>
                            </div>
                            {hasTestData(tc) && (
                              <div className="full">
                                <div className="tc-lbl">Test data</div>
                                <pre>{JSON.stringify(tc.test_data, null, 2)}</pre>
                              </div>
                            )}
                          </div>
                        </td>
                      </tr>
                    )}
                  </Fragment>
                );
              })
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function DebateTranscript({ debate }) {
  const rounds = [...new Set(debate.turns.map((t) => t.round))].sort((a, b) => a - b);
  return (
    <div className="debate">
      <div className="debate-summary">
        <span className={`badge ${debate.consensus_reached ? "badge-green" : "badge-red"}`}>
          {debate.consensus_reached ? "Consensus reached" : "Max rounds hit"}
        </span>
        <span className="badge badge-grey">{debate.rounds_used} round(s)</span>
        <span className="badge badge-grey">{debate.total_findings} finding(s)</span>
        <span className="badge badge-grey">{debate.revisions_made} revision(s)</span>
      </div>

      {rounds.map((round) => (
        <div className="debate-round" key={round}>
          <div className="round-label">Round {round}</div>
          {debate.turns
            .filter((t) => t.round === round)
            .map((turn) => (
              <DebateTurn key={turn.id} turn={turn} />
            ))}
        </div>
      ))}
    </div>
  );
}

function DebateTurn({ turn }) {
  const isReviewer = turn.speaker === "reviewer";
  const c = turn.content || {};
  return (
    <div className={`debate-turn ${isReviewer ? "turn-reviewer" : "turn-consensus"}`}>
      <div className="turn-head">
        <span className="speaker">{isReviewer ? "Reviewer" : "Consensus"}</span>
        {isReviewer && (
          <span className="muted">
            {c.needs_revision ? "requested changes" : "satisfied — no changes"}
          </span>
        )}
      </div>

      {isReviewer &&
        (c.findings?.length ? (
          <ul className="finding-list">
            {c.findings.map((f, i) => (
              <li className="finding" key={i}>
                <div className="finding-head">
                  <span className={`sev sev-${f.severity}`}>{f.severity}</span>
                  <span className="issue-type">{f.issue_type}</span>
                  {f.test_case_id && (
                    <span className="muted">on TC #{f.test_case_id}</span>
                  )}
                </div>
                <p>{f.description}</p>
                {f.suggestion && (
                  <p className="muted">
                    <strong>Fix:</strong> {f.suggestion}
                  </p>
                )}
              </li>
            ))}
          </ul>
        ) : (
          <p className="muted">No issues raised.</p>
        ))}

      {!isReviewer &&
        (c.resolutions?.length ? (
          <ul className="finding-list">
            {c.resolutions.map((r, i) => (
              <li className="finding" key={i}>
                <div className="finding-head">
                  <span className={`decision decision-${r.decision}`}>{r.decision}</span>
                  {r.test_case_id && (
                    <span className="muted">on TC #{r.test_case_id}</span>
                  )}
                </div>
                <p className="rationale">{r.rationale}</p>
                {r.revised_test_case && (
                  <p className="muted">
                    <strong>→</strong> {r.revised_test_case.title}
                  </p>
                )}
              </li>
            ))}
          </ul>
        ) : (
          <p className="muted">No resolutions.</p>
        ))}
    </div>
  );
}

function CoverageMatrix({ coverage }) {
  const items = coverage.items || [];
  return (
    <div className="coverage">
      <div className="debate-summary">
        <span
          className={`badge ${
            coverage.coverage_pct === 100 ? "badge-green" : "badge-red"
          }`}
        >
          {coverage.coverage_pct}% covered
        </span>
        <span className="badge badge-grey">
          {coverage.covered_count}/{coverage.total} criteria
        </span>
      </div>
      <table className="coverage-table">
        <thead>
          <tr>
            <th>Acceptance criterion</th>
            <th>Status</th>
            <th>Covering tests</th>
            <th>Notes</th>
          </tr>
        </thead>
        <tbody>
          {items.map((it) => (
            <tr key={it.acceptance_criterion_id}>
              <td>{it.criterion_text}</td>
              <td>
                <span className={`badge ${it.covered ? "badge-green" : "badge-red"}`}>
                  {it.covered ? "covered" : "gap"}
                </span>
              </td>
              <td>
                {it.covering_test_case_ids.length
                  ? it.covering_test_case_ids.map((id) => `#${id}`).join(", ")
                  : "—"}
              </td>
              <td className="muted">{it.gap_notes}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function scorePct(v) {
  return v == null ? "—" : `${Math.round(v * 100)}%`;
}

function QualityMatrix({ quality }) {
  const items = quality.items || [];
  const overall = Math.round((quality.overall_score || 0) * 100);
  return (
    <div className="coverage">
      <div className="debate-summary">
        <span className={`badge ${overall >= 70 ? "badge-green" : "badge-red"}`}>
          {overall}% overall quality
        </span>
        <span className="badge badge-grey">{quality.total} case(s)</span>
        <span className={`badge ${quality.duplicate_count ? "badge-red" : "badge-grey"}`}>
          {quality.duplicate_count} duplicate(s)
        </span>
      </div>
      <table className="coverage-table">
        <thead>
          <tr>
            <th>Test case</th>
            <th>Clarity</th>
            <th>Atomicity</th>
            <th>Traceability</th>
            <th>Dup?</th>
            <th>Notes</th>
          </tr>
        </thead>
        <tbody>
          {items.map((it) => (
            <tr key={it.test_case_id}>
              <td>
                <span className="muted">#{it.test_case_id}</span> {it.title}
              </td>
              <td>{scorePct(it.clarity_score)}</td>
              <td>{scorePct(it.atomicity_score)}</td>
              <td>{scorePct(it.traceability_score)}</td>
              <td>
                {it.duplicate_flag ? (
                  <span className="badge badge-red">dup</span>
                ) : (
                  <span className="muted">—</span>
                )}
              </td>
              <td className="muted">{it.notes}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function AnalysisList({ title, items, ordered }) {
  if (!items || items.length === 0) return null;
  const List = ordered ? "ol" : "ul";
  return (
    <div className="analysis-block">
      <h3>{title}</h3>
      <List>
        {items.map((it, idx) => (
          <li key={idx}>{it}</li>
        ))}
      </List>
    </div>
  );
}
