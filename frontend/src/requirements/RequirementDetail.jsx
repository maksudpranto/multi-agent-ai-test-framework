import { Fragment, useEffect, useMemo, useState } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { api, getModelSelection } from "../api/client";
import { REQ_TYPE_LABEL } from "./constants";
import UsagePanel from "../components/UsagePanel";
import ModelPicker from "../components/ModelPicker";

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

const SparkIcon = () => (
  <svg width="14" height="14" viewBox="0 0 16 16" fill="currentColor" aria-hidden>
    <path d="M8 1l1.35 3.65L13 6l-3.65 1.35L8 11 6.65 7.35 3 6l3.65-1.35z" />
    <path d="M13 10.5l.6 1.6 1.6.6-1.6.6-.6 1.6-.6-1.6-1.6-.6 1.6-.6z" opacity="0.75" />
  </svg>
);

// Every agent trigger looks the same: a gradient, spark-marked "AI-driven"
// button — so running a stage always reads as "the AI does this".
function AiRunButton({ onClick, disabled, busy, busyLabel, children }) {
  return (
    <button className="ai-btn" onClick={onClick} disabled={disabled}>
      {busy ? (
        <Busy>{busyLabel}</Busy>
      ) : (
        <>
          <SparkIcon />
          {children}
        </>
      )}
    </button>
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

// The page is a pipeline. Each tab is a stage the user can open; the numbered
// ones are the five agents that run in order. "Start" is the launch pad and
// "Export" is the takeaway.
export const REQ_TABS = [
  { key: "overview", label: "Start" },
  { key: "analyze", label: "Analyze", num: 1 },
  { key: "test", label: "Generate", num: 2 },
  { key: "review", label: "Review", num: 3 },
  { key: "coverage", label: "Coverage", num: 4 },
  { key: "quality", label: "Quality", num: 5 },
  { key: "export", label: "Export" },
];

// Plain-language "what it does / why it matters" for each agent stage — shown in
// a consistent header so the user always knows what a section is for.
const STAGE_META = {
  analyze: {
    num: 1,
    agent: "Analyst agent",
    what: "Turns your requirement into clear, testable acceptance criteria.",
    why: "Every test is built from these — sharper criteria, stronger suite.",
  },
  test: {
    num: 2,
    agent: "Generator agent",
    what: "Writes the test suite from the criteria — each case traced to one.",
    why: "The shippable suite, and the multi-agent output the framework improves.",
  },
  review: {
    num: 3,
    agent: "Reviewer ⇄ Consensus agents",
    what: "Two agents debate the suite: one critiques, the other revises or adds cases.",
    why: "The core idea — it catches gaps a single AI pass misses.",
  },
  coverage: {
    num: 4,
    agent: "Validator agent",
    what: "Matches every criterion to the tests that verify it, and flags the gaps.",
    why: "Proves nothing in the requirement goes untested.",
  },
  quality: {
    num: 5,
    agent: "Quality agent",
    what: "Scores each test on clarity, atomicity and traceability; flags duplicates.",
    why: "The final verdict on how good the suite really is.",
  },
};

// Consistent stage header: number badge, agent name, what/why, status + action.
function StageHeader({ meta, status, action }) {
  return (
    <div className="stage-head">
      <div className="stage-num">{meta.num}</div>
      <div className="stage-info">
        <div className="stage-agent">
          <span>{meta.agent}</span>
          {status}
        </div>
        <p className="stage-what">{meta.what}</p>
        <p className="stage-why">
          <b>Why it matters:</b> {meta.why}
        </p>
      </div>
      <div className="stage-actions">{action}</div>
    </div>
  );
}

function StatusPill({ done, label }) {
  return done ? (
    <span className="stpill done">✓ {label}</span>
  ) : (
    <span className="stpill idle">
      <span className="stpill-dot" aria-hidden />
      Not run yet
    </span>
  );
}

// The pipeline stepper across the top: order + status + key result, doubles as
// the tab navigation.
function PipelineStepper({ tabs, active, onPick, stageDone, stageResult }) {
  return (
    <div className="stepper" role="tablist">
      {tabs.map((t) => {
        const done = !!stageDone[t.key];
        return (
          <button
            key={t.key}
            role="tab"
            aria-selected={active === t.key}
            className={`step ${active === t.key ? "active" : ""} ${done ? "done" : ""}`}
            onClick={() => onPick(t.key)}
          >
            <span className="step-badge">{done ? "✓" : t.num || "•"}</span>
            <span className="step-txt">
              <span className="step-label">{t.label}</span>
              {stageResult[t.key] && (
                <span className="step-result">{stageResult[t.key]}</span>
              )}
            </span>
          </button>
        );
      })}
    </div>
  );
}

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
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [running, setRunning] = useState(false);
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
  const [selectedProvider, setSelectedProvider] = useState(getModelSelection()?.provider || null);

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
        const res = await paced(api.runRequirementAnalysis(projectId, requirementId));
        setResult(res);
        crit = res?.acceptance_criteria || [];
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
  const qualityPct = quality ? Math.round((quality.overall_score || 0) * 100) : null;

  const stageDone = {
    analyze: !!(analysis || criteria.length),
    test: multiCases.length > 0,
    review: !!debate,
    coverage: !!coverage,
    quality: !!quality,
  };
  const stageResult = {
    analyze: criteria.length ? `${criteria.length} criteria` : "",
    test: multiCases.length ? `${multiCases.length} cases` : "",
    review: debate ? (debate.consensus_reached ? "consensus" : `${debate.rounds_used} rounds`) : "",
    coverage: coverage ? `${coverage.coverage_pct}%` : "",
    quality: qualityPct != null ? `${qualityPct}%` : "",
  };

  return (
    <div className="content">
      <div className="page rq">
        <p className="crumb">
          <Link to="/projects">Projects</Link>
          <span className="sep">/</span>
          <Link to={`/projects/${projectId}`}>Requirements</Link>
          <span className="sep">/</span>
          <span>{story?.title}</span>
        </p>
        <header className="rq-head">
          <div className="rq-head-main">
            <h1>{story?.title}</h1>
            {story && (
              <div className="case-badges">
                <span className="chip chip-accent">
                  {REQ_TYPE_LABEL[story.req_type] || story.req_type}
                </span>
                {story.source_filename && (
                  <span className="chip chip-grey">📎 {story.source_filename}</span>
                )}
              </div>
            )}
          </div>
          <ModelPicker onProviderChange={setSelectedProvider} />
        </header>

        <UsagePanel providerFilter={selectedProvider} />

        <div className="run-bar">
          <div className="run-bar-main">
            <button className="btn-primary run-btn" onClick={onRunAll} disabled={runningAll}>
              {runningAll ? (
                <><span className="spinner" /> Working…</>
              ) : generation ? (
                "▶ Re-run full pipeline"
              ) : (
                "▶ Run full pipeline"
              )}
            </button>
            <span className="run-bar-hint">
              One click runs all five agents in order — Analyze → Generate → Review →
              Coverage → Quality — turning this requirement into a proven test suite.
            </span>
          </div>
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
                      {current ? `Step ${done + 1} of ${total} · ${current}` : "Finishing up"}
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
        </div>

        <PipelineStepper
          tabs={REQ_TABS}
          active={activeTab}
          onPick={setTab}
          stageDone={stageDone}
          stageResult={stageResult}
        />

        {error && <p className="error" style={{ margin: "0 0 4px" }}>{error}</p>}

        {/* ---------- Start: requirement + one-click run ---------- */}
        {activeTab === "overview" && (
          <>
            <section className="section req-section">
              <h2>Requirement</h2>
              <div className="req-body">
                {(story?.raw_text || "")
                  .split(/\n\s*\n/)
                  .map((para) => para.replace(/\s*\n\s*/g, " ").trim())
                  .filter(Boolean)
                  .map((para, i) => (
                    <p key={i} className="story-text">{para}</p>
                  ))}
              </div>
            </section>

            <section className="section auto-run">
              <div className="auto-run-head">
                <span className="auto-run-ic" aria-hidden>⚡</span>
                <div className="auto-run-txt">
                  <h2>Watch the AI run itself</h2>
                  <p>
                    Same agents, same test suite — but the AI chooses which one runs
                    next at each step, and shows why.
                  </p>
                </div>
                <button
                  className="auto-run-btn"
                  onClick={onOrchestrate}
                  disabled={orchestrating || runningAll}
                >
                  {orchestrating ? <Busy>Working…</Busy> : "Let the AI drive ▶"}
                </button>
              </div>
              {orchestration && <OrchestrationTrace data={orchestration} />}
            </section>
          </>
        )}

        {/* ---------- 1 · Analyze ---------- */}
        {activeTab === "analyze" && (
          <section className="section stage">
            <StageHeader
              meta={STAGE_META.analyze}
              status={
                <StatusPill done={stageDone.analyze} label={stageResult.analyze} />
              }
              action={
                <AiRunButton
                  onClick={onAnalyze}
                  disabled={running || runningAll}
                  busy={running}
                  busyLabel="Analyzing…"
                >
                  {analysis ? "Re-run analysis" : "Run analysis"}
                </AiRunButton>
              }
            />

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

            {!stageDone.analyze && (
              <p className="muted">
                Run analysis to turn the requirement into testable acceptance
                criteria — the input for every stage that follows.
              </p>
            )}
          </section>
        )}

        {/* ---------- 2 · Generate ---------- */}
        {activeTab === "test" && (
          <>
            <section className="section stage">
              <StageHeader
                meta={STAGE_META.test}
                status={<StatusPill done={stageDone.test} label={stageResult.test} />}
                action={
                  mode === "multi" ? (
                    <AiRunButton
                      onClick={onGenerate}
                      disabled={criteria.length === 0 || generating || runningAll}
                      busy={generating}
                      busyLabel="Generating…"
                    >
                      {multiCases.length ? "Re-generate" : "Generate test cases"}
                    </AiRunButton>
                  ) : (
                    <AiRunButton
                      onClick={onBaseline}
                      disabled={baselining}
                      busy={baselining}
                      busyLabel="Running…"
                    >
                      Run baseline
                    </AiRunButton>
                  )
                }
              />

              <div className="mode-toggle sub" role="tablist">
                <button
                  className={`mode-btn ${mode === "multi" ? "active" : ""}`}
                  onClick={() => setMode("multi")}
                >
                  Multi-agent suite
                </button>
                <button
                  className={`mode-btn ${mode === "baseline" ? "active" : ""}`}
                  onClick={() => setMode("baseline")}
                >
                  Single-AI baseline (compare)
                </button>
              </div>

              {mode === "multi" ? (
                <>
                  {criteria.length === 0 && (
                    <p className="muted sub-note">
                      Needs acceptance criteria first — run <b>1 · Analyze</b> (or paste
                      criteria there).
                    </p>
                  )}
                  {multiCases.length === 0 ? (
                    <p className="muted">
                      Generate a full, traceable test suite from the acceptance criteria.
                    </p>
                  ) : (
                    <TestCaseTable cases={multiCases} showTrace />
                  )}
                </>
              ) : (
                <>
                  <p className="muted sub-note">
                    The control arm: one AI call turns the story straight into tests —
                    no analysis, no debate, no traceability. This is exactly what the
                    multi-agent suite is measured against.
                  </p>
                  {baselineCases.length === 0 ? (
                    <p className="muted">Run the baseline to generate tests in one step.</p>
                  ) : (
                    <TestCaseTable cases={baselineCases} />
                  )}
                </>
              )}
            </section>

            {mode === "multi" && multiCases.length > 0 && (
              <section className="section optional-card">
                <div className="section-head">
                  <h2>Optional · Prioritize the suite</h2>
                  <AiRunButton
                    onClick={onPrioritize}
                    disabled={prioritizing}
                    busy={prioritizing}
                    busyLabel="Prioritizing…"
                  >
                    Prioritize suite
                  </AiRunButton>
                </div>
                <p className="muted mode-note">
                  The Prioritizer ranks cases by business importance and assigns a
                  production-impact severity, so a time-pressed team knows what to run
                  first. Ranked cases sort to the top of the table above.
                </p>
                {multiCases.some((tc) => tc.rank != null) && (
                  <p className="muted">
                    Ranked {multiCases.filter((tc) => tc.rank != null).length} case(s).
                  </p>
                )}
              </section>
            )}
          </>
        )}

        {/* ---------- 3 · Review ---------- */}
        {activeTab === "review" && (
          <section className="section stage">
            <StageHeader
              meta={STAGE_META.review}
              status={<StatusPill done={stageDone.review} label={stageResult.review} />}
              action={
                <AiRunButton
                  onClick={onReviewConsensus}
                  disabled={multiCases.length === 0 || reviewing || runningAll}
                  busy={reviewing}
                  busyLabel="Debating…"
                >
                  {debate ? "Re-run debate" : "Run review & consensus"}
                </AiRunButton>
              }
            />
            {debate?.error && <p className="error">{debate.error}</p>}
            {multiCases.length === 0 ? (
              <p className="muted">
                Needs a test suite first — run <b>2 · Generate</b>, then run the debate.
              </p>
            ) : !debate ? (
              <p className="muted">
                Run the debate to watch the agents critique and revise the suite.
              </p>
            ) : (
              <DebateTranscript debate={debate} />
            )}
          </section>
        )}

        {/* ---------- 4 · Coverage ---------- */}
        {activeTab === "coverage" && (
          <section className="section stage">
            <StageHeader
              meta={STAGE_META.coverage}
              status={<StatusPill done={stageDone.coverage} label={stageResult.coverage ? `${coverage.covered_count}/${coverage.total} covered` : ""} />}
              action={
                <AiRunButton
                  onClick={onCoverage}
                  disabled={multiCases.length === 0 || analysingCoverage || runningAll}
                  busy={analysingCoverage}
                  busyLabel="Analysing…"
                >
                  {coverage ? "Re-run coverage" : "Analyse coverage"}
                </AiRunButton>
              }
            />
            {coverage?.error && <p className="error">{coverage.error}</p>}
            {multiCases.length === 0 ? (
              <p className="muted">
                Needs a test suite first — run <b>2 · Generate</b>, then analyse coverage.
              </p>
            ) : !coverage ? (
              <p className="muted">
                Analyse coverage to see the requirement-to-test matrix and any gaps.
              </p>
            ) : (
              <CoverageMatrix coverage={coverage} />
            )}
          </section>
        )}

        {/* ---------- 5 · Quality ---------- */}
        {activeTab === "quality" && (
          <section className="section stage">
            <StageHeader
              meta={STAGE_META.quality}
              status={<StatusPill done={stageDone.quality} label={qualityPct != null ? `${qualityPct}% overall` : ""} />}
              action={
                <AiRunButton
                  onClick={onQuality}
                  disabled={multiCases.length === 0 || evaluatingQuality || runningAll}
                  busy={evaluatingQuality}
                  busyLabel="Evaluating…"
                >
                  {quality ? "Re-run quality" : "Evaluate quality"}
                </AiRunButton>
              }
            />
            {quality?.error && <p className="error">{quality.error}</p>}
            {multiCases.length === 0 ? (
              <p className="muted">
                Needs a test suite first — run <b>2 · Generate</b>, then evaluate quality.
              </p>
            ) : !quality ? (
              <p className="muted">
                Evaluate quality to score the suite and detect duplicates.
              </p>
            ) : (
              <QualityMatrix quality={quality} cases={multiCases} />
            )}
          </section>
        )}

        {/* ---------- Export ---------- */}
        {activeTab === "export" && (
          <section className="section">
            <h2>Export test design package</h2>
            <p className="mode-note">
              Download the complete package — requirement, acceptance criteria, test
              cases with quality scores, and the coverage matrix — for the latest
              multi-agent run.
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
  { fmt: "pdf", label: "PDF" },
  { fmt: "xlsx", label: "Excel" },
  { fmt: "md", label: "Markdown" },
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
  const findings = debate.total_findings;
  const revisions = debate.revisions_made;
  const clean = findings === 0;
  const ok = clean || debate.consensus_reached;
  const headline = clean
    ? "The Reviewer checked every test case and raised no issues — the suite passed on the first look, so nothing was changed."
    : `The Reviewer flagged ${findings} issue${findings === 1 ? "" : "s"}, and the Consensus agent made ${revisions} change${revisions === 1 ? "" : "s"} in response. ${
        debate.consensus_reached
          ? `They agreed after ${debate.rounds_used} round${debate.rounds_used === 1 ? "" : "s"}.`
          : `The debate stopped at its ${debate.rounds_used}-round limit before fully agreeing.`
      }`;

  return (
    <div className="debate">
      <div className={`debate-outcome ${ok ? "ok" : "warn"}`}>
        <span className="dbo-ic">{ok ? "✓" : "!"}</span>
        <p>{headline}</p>
      </div>

      <div className="debate-tiles">
        <div className="dbt">
          <b>{debate.rounds_used}</b>
          <span>round{debate.rounds_used === 1 ? "" : "s"} of back-and-forth</span>
        </div>
        <div className="dbt">
          <b>{findings}</b>
          <span>issue{findings === 1 ? "" : "s"} the Reviewer raised</span>
        </div>
        <div className="dbt">
          <b>{revisions}</b>
          <span>change{revisions === 1 ? "" : "s"} made to the suite</span>
        </div>
      </div>

      {clean ? (
        <div className="debate-clean">
          <span className="dbc-ic" aria-hidden>🛡️</span>
          <div>
            <b>Nothing to fix</b>
            <p>
              The Reviewer read through the suite and was satisfied straight away.
              When it spots weak, missing, or duplicate cases, they show up here as a
              back-and-forth with the Consensus agent — who revises or adds cases in
              response.
            </p>
          </div>
        </div>
      ) : (
        <>
          <p className="debate-intro">The full exchange, round by round:</p>
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
        </>
      )}
    </div>
  );
}

function DebateTurn({ turn }) {
  const isReviewer = turn.speaker === "reviewer";
  const c = turn.content || {};
  const sub = isReviewer
    ? c.needs_revision
      ? "flagged issues"
      : "satisfied — no changes"
    : c.resolutions?.length
      ? "responded with changes"
      : "no changes needed";
  return (
    <div className={`debate-turn ${isReviewer ? "turn-reviewer" : "turn-consensus"}`}>
      <div className="turn-head">
        <span className="speaker">{isReviewer ? "Reviewer" : "Consensus"}</span>
        <span className="turn-role">{isReviewer ? "critic" : "fixer"}</span>
        <span className="turn-sub">{sub}</span>
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
  const covered = coverage.covered_count;
  const total = coverage.total;
  const gaps = total - covered;
  const full = gaps === 0;
  const headline = full
    ? "Every acceptance criterion is verified by at least one test — the suite fully covers the requirement, with no gaps."
    : `${covered} of ${total} criteria are verified by tests. ${gaps} ${
        gaps === 1 ? "criterion has" : "criteria have"
      } no test yet — ${gaps === 1 ? "that's the gap" : "those are the gaps"} to fill.`;

  return (
    <div className="coverage">
      <div className={`debate-outcome ${full ? "ok" : "warn"}`}>
        <span className="dbo-ic">{full ? "✓" : "!"}</span>
        <p>{headline}</p>
      </div>

      <div className="debate-tiles">
        <div className="dbt">
          <b>{coverage.coverage_pct}%</b>
          <span>of the requirement covered</span>
        </div>
        <div className="dbt">
          <b>{covered}/{total}</b>
          <span>criteria with a test</span>
        </div>
        <div className="dbt">
          <b>{gaps}</b>
          <span>gap{gaps === 1 ? "" : "s"} — untested criteria</span>
        </div>
      </div>

      <p className="debate-intro">Each acceptance criterion, and the tests that verify it:</p>
      <ul className="cov-list">
        {items.map((it, idx) => {
          const n = it.covering_test_case_ids.length;
          return (
            <li className={`cov-item ${it.covered ? "" : "gap"}`} key={it.acceptance_criterion_id}>
              <span className={`cov-check ${it.covered ? "ok" : "gap"}`} aria-hidden>
                {it.covered ? "✓" : "!"}
              </span>
              <div className="cov-body">
                <div className="cov-crit">
                  <code className="cov-ac">AC{idx + 1}</code>
                  <span>{it.criterion_text}</span>
                </div>
                {!it.covered && (
                  <div className="cov-note">
                    {it.gap_notes || "No test verifies this criterion yet."}
                  </div>
                )}
              </div>
              <span className={`cov-tests ${it.covered ? "" : "none"}`}>
                {n ? `${n} test${n === 1 ? "" : "s"}` : "no test"}
              </span>
            </li>
          );
        })}
      </ul>
    </div>
  );
}

function scorePct(v) {
  return v == null ? null : Math.round(v * 100);
}

// A small labelled score chip, coloured by how good the score is.
function QScore({ label, pct }) {
  const tone = pct == null ? "na" : pct >= 80 ? "ok" : pct >= 50 ? "warn" : "bad";
  return (
    <span className={`qscore ${tone}`} title={label}>
      <b>{pct == null ? "—" : `${pct}%`}</b>
      <span>{label}</span>
    </span>
  );
}

// The duplicate note is free text that references other cases by their internal
// id (e.g. "overlaps with test case 2456"). Users never see those ids, so we
// swap any id that matches a case in the suite for that case's title — turning
// the note into something actionable ("overlaps with 'Attempt login…'").
function humanizeDupNote(note, byId) {
  if (!note) return note;
  const parts = note.split(/(\d+)/);
  return parts.map((p, i) =>
    /^\d+$/.test(p) && byId[Number(p)] ? (
      <b key={i} className="ql-ref">“{byId[Number(p)]}”</b>
    ) : (
      <span key={i}>{p}</span>
    )
  );
}

function QualityMatrix({ quality, cases = [] }) {
  const items = quality.items || [];
  const byId = {};
  for (const c of cases) byId[c.id] = c.title;
  const overall = Math.round((quality.overall_score || 0) * 100);
  const dups = quality.duplicate_count || 0;
  const good = overall >= 70;
  const bannerTone = good && dups === 0 ? "ok" : "warn";
  const headline =
    `${good ? "The suite scores well" : "The suite scores below the bar"} — ${overall}% overall: the tests are clear, focused (one thing each), and traceable.` +
    (dups
      ? ` ${dups} possible duplicate${dups === 1 ? "" : "s"} flagged to review.`
      : " No duplicates found.");

  // Split cases into the few that need attention (a duplicate, or a sub-100
  // score) and the rest that passed cleanly — so the page leads with what
  // matters instead of 15 identical "100%" cards.
  const rows = items.map((it) => {
    const clarity = scorePct(it.clarity_score);
    const atomicity = scorePct(it.atomicity_score);
    const traceability = scorePct(it.traceability_score);
    const nums = [clarity, atomicity, traceability].filter((v) => v != null);
    const minV = nums.length ? Math.min(...nums) : null;
    const imperfect = minV != null && minV < 100;
    const weak = minV != null && minV < 90;
    const flagged = it.duplicate_flag || weak;
    const genericNote = it.notes && /well[-\s]?formed/i.test(it.notes);
    let note = null;
    if (it.duplicate_flag) {
      note = it.notes
        ? humanizeDupNote(it.notes, byId)
        : "Flagged as a possible duplicate of another test case.";
    } else if (it.notes && !genericNote) {
      note = it.notes;
    }
    return { it, clarity, atomicity, traceability, flagged, imperfect, note };
  });
  const flaggedRows = rows.filter((r) => r.flagged);
  const cleanRows = rows.filter((r) => !r.flagged);

  const qTabs = [["all", "All", items.length]];
  if (flaggedRows.length) qTabs.push(["flagged", "Needs a look", flaggedRows.length]);
  if (cleanRows.length) qTabs.push(["clean", "Looks good", cleanRows.length]);
  const [qf, setQf] = useState("all");

  return (
    <div className="coverage">
      <div className={`debate-outcome ${bannerTone}`}>
        <span className="dbo-ic">{bannerTone === "ok" ? "✓" : "!"}</span>
        <p>{headline}</p>
      </div>

      <div className="debate-tiles">
        <div className="dbt">
          <b>{overall}%</b>
          <span>overall quality score</span>
        </div>
        <div className="dbt">
          <b>{quality.total}</b>
          <span>test cases scored</span>
        </div>
        <div className="dbt">
          <b>{dups}</b>
          <span>possible duplicate{dups === 1 ? "" : "s"}</span>
        </div>
      </div>

      <div className="tc-tabs ql-tabs">
        {qTabs.map(([key, label, n]) => (
          <button
            key={key}
            className={qf === key ? "active" : ""}
            onClick={() => setQf(key)}
          >
            {label} <span className="n">{n}</span>
          </button>
        ))}
      </div>

      {/* All — every case as a full scorecard (the original detailed view) */}
      {qf === "all" && (
        <ul className="ql-list">
          {rows.map((r) => (
            <li className={`ql-item ${r.it.duplicate_flag ? "dup" : ""}`} key={r.it.test_case_id}>
              <div className="ql-main">
                <div className="ql-title-line">
                  <span className="ql-title">{r.it.title}</span>
                  {r.it.duplicate_flag && <span className="ql-dup">possible duplicate</span>}
                </div>
                {r.note && <div className="ql-note">{r.note}</div>}
              </div>
              <div className="ql-scores">
                <QScore label="Clarity" pct={r.clarity} />
                <QScore label="Atomicity" pct={r.atomicity} />
                <QScore label="Traceability" pct={r.traceability} />
              </div>
            </li>
          ))}
        </ul>
      )}

      {/* Needs a look — flagged cases only (chips only when actually imperfect) */}
      {qf === "flagged" && (
        <ul className="ql-list needs">
          {flaggedRows.map((r) => (
            <li className={`ql-item ${r.it.duplicate_flag ? "dup" : ""}`} key={r.it.test_case_id}>
              <div className="ql-main">
                <div className="ql-title-line">
                  <span className="ql-title">{r.it.title}</span>
                  {r.it.duplicate_flag && <span className="ql-dup">possible duplicate</span>}
                </div>
                {r.note && <div className="ql-note">{r.note}</div>}
              </div>
              {r.imperfect && (
                <div className="ql-scores">
                  <QScore label="Clarity" pct={r.clarity} />
                  <QScore label="Atomicity" pct={r.atomicity} />
                  <QScore label="Traceability" pct={r.traceability} />
                </div>
              )}
            </li>
          ))}
        </ul>
      )}

      {/* Looks good — clean cases as a light grid of check-tiles */}
      {qf === "clean" && (
        <ul className="ql-pass">
          {cleanRows.map((r) => (
            <li className="ql-pass-item" key={r.it.test_case_id}>
              <span className="ql-pass-ic" aria-hidden>✓</span>
              <span className="ql-pass-title">{r.it.title}</span>
            </li>
          ))}
        </ul>
      )}
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
