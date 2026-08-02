import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "../api/client";
import { PIPELINE_STAGES } from "../pipeline/stages";
import { REQ_TYPE_LABEL } from "./constants";

export default function RequirementDetail() {
  const { projectId, requirementId } = useParams();
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
      setResult(await api.runRequirementAnalysis(projectId, requirementId));
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
      setResult(await api.submitAcceptanceCriteria(projectId, requirementId, criteria));
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
      setGeneration(await api.generateTestCases(projectId, requirementId));
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
      const d = await api.runReviewConsensus(projectId, requirementId);
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
      setGeneration(await api.prioritize(projectId, requirementId));
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
      setCoverage(await api.runCoverage(projectId, requirementId));
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
      setQuality(await api.runQuality(projectId, requirementId));
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
      setBaseline(await api.runBaseline(projectId, requirementId));
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
          <Link to={`/projects/${projectId}`}>Project</Link> /{" "}
          {story?.module_id && (
            <>
              <Link to={`/projects/${projectId}/modules/${story.module_id}`}>Module</Link> /{" "}
            </>
          )}
          {story?.title}
        </p>
        <h1>{story?.title}</h1>
        {story && (
          <div className="case-badges" style={{ marginBottom: 8 }}>
            <span className="badge badge-blue">{REQ_TYPE_LABEL[story.req_type] || story.req_type}</span>
            <span className="badge badge-grey">priority: {story.priority}</span>
            <span className="badge badge-grey">status: {story.status}</span>
            {story.source_filename && (
              <span className="badge badge-grey">📎 {story.source_filename}</span>
            )}
          </div>
        )}

        <section className="section">
          <h2>User story</h2>
          <p className="story-text">{story?.raw_text}</p>
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
                <button onClick={onAnalyze} disabled={running}>
                  {running ? "Analyzing…" : analysis ? "Re-run analysis" : "Run analysis"}
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
                  {submittingAc ? "Saving…" : "Use these criteria"}
                </button>
              </div>
            </>
          )}

          {error && <p className="error">{error}</p>}
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
                <button onClick={onGenerate} disabled={criteria.length === 0 || generating}>
                  {generating ? "Generating…" : "Generate test cases"}
                </button>
              </div>
              {multiCases.length === 0 ? (
                <p className="muted">
                  Provide acceptance criteria (analyse a requirement or paste them
                  directly), then generate a full, traceable test suite.
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

        {mode === "multi" && (
          <section className="section">
            <div className="section-head">
              <h2>Prioritization</h2>
              <button onClick={onPrioritize} disabled={multiCases.length === 0 || prioritizing}>
                {prioritizing ? "Prioritizing…" : "Prioritize suite"}
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

        {mode === "multi" && (
          <section className="section">
            <div className="section-head">
              <h2>Coverage &amp; Validation</h2>
              <button onClick={onCoverage} disabled={multiCases.length === 0 || analysingCoverage}>
                {analysingCoverage ? "Analysing…" : coverage ? "Re-run coverage" : "Analyse coverage"}
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

        {mode === "multi" && (
          <section className="section">
            <div className="section-head">
              <h2>Quality Report</h2>
              <button onClick={onQuality} disabled={multiCases.length === 0 || evaluatingQuality}>
                {evaluatingQuality ? "Evaluating…" : quality ? "Re-run quality" : "Evaluate quality"}
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
  const hasData =
    tc.test_data &&
    (Array.isArray(tc.test_data)
      ? tc.test_data.length > 0
      : Object.keys(tc.test_data).length > 0);
  return (
    <article className="generated-case">
      <div className="generated-case-head">
        <h3>{tc.title}</h3>
        <div className="case-badges">
          {tc.rank != null && (
            <span className="badge badge-rank">#{tc.rank}</span>
          )}
          {tc.type && <span className={`badge type-${tc.type}`}>{tc.type}</span>}
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
          {tc.severity && (
            <span className={`badge sev-badge sev-${tc.severity}`}>{tc.severity}</span>
          )}
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
      {hasData && (
        <div className="test-data">
          <span className="test-data-label">Test data</span>
          <pre>{JSON.stringify(tc.test_data, null, 2)}</pre>
        </div>
      )}
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
