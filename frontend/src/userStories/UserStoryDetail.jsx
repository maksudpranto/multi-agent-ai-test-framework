import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "../api/client";
import { PIPELINE_STAGES } from "../pipeline/stages";

export default function UserStoryDetail() {
  const { projectId, storyId } = useParams();
  const [story, setStory] = useState(null);
  const [result, setResult] = useState(null);
  const [generation, setGeneration] = useState(null);
  const [debate, setDebate] = useState(null);
  const [baseline, setBaseline] = useState(null);
  const [mode, setMode] = useState("multi"); // "multi" | "baseline"
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [running, setRunning] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [reviewing, setReviewing] = useState(false);
  const [baselining, setBaselining] = useState(false);

  useEffect(() => {
    setLoading(true);
    Promise.all([
      api.getUserStory(projectId, storyId),
      api.getLatestAnalysis(projectId, storyId).catch(() => null),
      api.getLatestTestCases(projectId, storyId).catch(() => null),
      api.getLatestReviewConsensus(projectId, storyId).catch(() => null),
      api.getLatestBaseline(projectId, storyId).catch(() => null),
    ])
      .then(([s, r, g, d, b]) => {
        setStory(s);
        setResult(r);
        setGeneration(g);
        setDebate(d);
        setBaseline(b);
      })
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, [projectId, storyId]);

  async function onAnalyze() {
    setRunning(true);
    setError("");
    try {
      setResult(await api.runRequirementAnalysis(projectId, storyId));
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
      setGeneration(await api.generateTestCases(projectId, storyId));
      setDebate(null); // stale once test cases change
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
      const d = await api.runReviewConsensus(projectId, storyId);
      setDebate(d);
      // consensus can add/revise cases — refresh the multi-agent set
      setGeneration(await api.getLatestTestCases(projectId, storyId));
    } catch (err) {
      setError(err.message);
    } finally {
      setReviewing(false);
    }
  }

  async function onBaseline() {
    setBaselining(true);
    setError("");
    try {
      setBaseline(await api.runBaseline(projectId, storyId));
    } catch (err) {
      setError(err.message);
    } finally {
      setBaselining(false);
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
        <p className="breadcrumb">
          <Link to="/">Home</Link> /{" "}
          <Link to={`/projects/${projectId}`}>Project</Link> / {story?.title}
        </p>
        <h1>{story?.title}</h1>

        <section className="section">
          <h2>User story</h2>
          <p className="story-text">{story?.raw_text}</p>
        </section>

        <section className="section">
          <div className="section-head">
            <h2>Requirement Analysis</h2>
            <button onClick={onAnalyze} disabled={running}>
              {running ? "Analyzing…" : analysis ? "Re-run analysis" : "Run analysis"}
            </button>
          </div>

          {error && <p className="error">{error}</p>}
          {result?.error && <p className="error">{result.error}</p>}

          {!analysis && !result?.error && (
            <p className="muted">
              Run the analysis to break this story into a structured, testable
              specification.
            </p>
          )}

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
        </section>

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
                <button onClick={onGenerate} disabled={!analysis || generating}>
                  {generating ? "Generating…" : "Generate test cases"}
                </button>
              </div>
              {multiCases.length === 0 ? (
                <p className="muted">
                  Run requirement analysis, then generate traceable test cases.
                </p>
              ) : (
                <div className="generated-cases">
                  {multiCases.map((tc) => (
                    <TestCaseCard key={tc.id} tc={tc} showTrace />
                  ))}
                </div>
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
                  {baselining ? "Running…" : "Run single-LLM baseline"}
                </button>
              </div>
              {baselineCases.length === 0 ? (
                <p className="muted">
                  Run the baseline to generate test cases from the story in one step.
                </p>
              ) : (
                <div className="generated-cases">
                  {baselineCases.map((tc) => (
                    <TestCaseCard key={tc.id} tc={tc} />
                  ))}
                </div>
              )}
            </>
          )}
        </section>

        {mode === "multi" && (
          <section className="section">
            <div className="section-head">
              <h2>Review &amp; Consensus — multi-agent debate</h2>
              <button
                onClick={onReviewConsensus}
                disabled={multiCases.length === 0 || reviewing}
              >
                {reviewing ? "Debating…" : debate ? "Re-run debate" : "Run review & consensus"}
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

        <section className="section">
          <h2>Pipeline stages</h2>
          <ol className="stepper">
            {PIPELINE_STAGES.map((stage, i) => (
              <li
                key={stage.key}
                className={`step ${stage.implemented ? "done" : "pending"}`}
              >
                <span className="step-index">{i + 1}</span>
                <span className="step-label">{stage.label}</span>
                <span className="step-status">
                  {stage.implemented ? "Ready" : "Not yet implemented"}
                </span>
              </li>
            ))}
          </ol>
        </section>
      </div>
    </div>
  );
}

function TestCaseCard({ tc, showTrace }) {
  return (
    <article className="generated-case">
      <div className="generated-case-head">
        <h3>{tc.title}</h3>
        <div className="case-badges">
          {tc.generated_by === "consensus" && (
            <span className="badge badge-green">consensus v{tc.version}</span>
          )}
          {tc.status === "reviewer_flagged" && (
            <span className="badge badge-red">flagged</span>
          )}
          {showTrace &&
            (tc.traces_to ? (
              <span className="badge badge-blue">AC #{tc.traces_to}</span>
            ) : (
              <span className="badge badge-grey">no trace</span>
            ))}
          <span className="badge badge-grey">{tc.priority}</span>
        </div>
      </div>
      <ol>
        {tc.steps?.map((step, index) => (
          <li key={index}>{step}</li>
        ))}
      </ol>
      <p>
        <strong>Expected:</strong> {tc.expected_result}
      </p>
    </article>
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
