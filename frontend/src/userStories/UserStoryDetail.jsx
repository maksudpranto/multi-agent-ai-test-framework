import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "../api/client";
import { PIPELINE_STAGES } from "../pipeline/stages";

export default function UserStoryDetail() {
  const { projectId, storyId } = useParams();
  const [story, setStory] = useState(null);
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [running, setRunning] = useState(false);

  useEffect(() => {
    setLoading(true);
    Promise.all([
      api.getUserStory(projectId, storyId),
      api.getLatestAnalysis(projectId, storyId).catch(() => null),
    ])
      .then(([s, r]) => {
        setStory(s);
        setResult(r);
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

        <section className="section">
          <h2>Generation pipeline</h2>
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
