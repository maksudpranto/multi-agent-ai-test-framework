import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "../api/client";
import { PIPELINE_STAGES } from "../pipeline/stages";

export default function UserStoryDetail() {
  const { projectId, storyId } = useParams();
  const [story, setStory] = useState(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    api
      .getUserStory(projectId, storyId)
      .then(setStory)
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, [projectId, storyId]);

  if (loading) return <div className="page"><p className="muted">Loading…</p></div>;
  if (error) return <div className="page"><p className="error">{error}</p></div>;

  return (
    <div className="page">
      <p className="breadcrumb">
        <Link to="/">Projects</Link> /{" "}
        <Link to={`/projects/${projectId}`}>Project</Link> / {story?.title}
      </p>
      <h1>{story?.title}</h1>

      <section className="panel">
        <h2>User Story</h2>
        <p className="story-text">{story?.raw_text}</p>
      </section>

      <section className="panel">
        <h2>Generation Pipeline</h2>
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
        <p className="muted">
          The multi-agent stages will run here in upcoming build phases.
        </p>
      </section>
    </div>
  );
}
