import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "../api/client";

export default function ProjectDetail() {
  const { projectId } = useParams();
  const [project, setProject] = useState(null);
  const [stories, setStories] = useState([]);
  const [title, setTitle] = useState("");
  const [rawText, setRawText] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  async function load() {
    setLoading(true);
    try {
      const [p, s] = await Promise.all([
        api.getProject(projectId),
        api.listUserStories(projectId),
      ]);
      setProject(p);
      setStories(s);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, [projectId]);

  async function onCreate(e) {
    e.preventDefault();
    setError("");
    try {
      await api.createUserStory(projectId, title, rawText);
      setTitle("");
      setRawText("");
      await load();
    } catch (err) {
      setError(err.message);
    }
  }

  async function onDelete(id) {
    if (!confirm("Delete this user story?")) return;
    await api.deleteUserStory(projectId, id);
    await load();
  }

  if (loading)
    return (
      <div className="content">
        <p className="muted">Loading…</p>
      </div>
    );

  return (
    <div className="content project-content">
      <div className="page project-page">
        <p className="breadcrumb">
          <Link to="/">Home</Link> / {project?.name}
        </p>
        <header className="project-page-head">
          <div>
            <div className="eyebrow">Project workspace</div>
            <h1>{project?.name}</h1>
            <p>{project?.description || "Create and prepare requirements for analysis."}</p>
          </div>
          <div className="story-count">
            <strong>{stories.length}</strong>
            <span>{stories.length === 1 ? "user story" : "user stories"}</span>
          </div>
        </header>

        <div className="stories-workspace">
          <aside className="story-composer">
            <div className="panel-kicker">New requirement</div>
            <h2>Add a user story</h2>
            <p className="muted">Describe the user need and the expected outcome.</p>
            <form className="story-form" onSubmit={onCreate}>
              <label>
                Story title
                <input
                  placeholder="e.g. Secure sign in"
                  value={title}
                  onChange={(e) => setTitle(e.target.value)}
                  required
                />
              </label>
              <label>
                Requirement
                <textarea
                  placeholder="As a user, I want to… so that…"
                  value={rawText}
                  onChange={(e) => setRawText(e.target.value)}
                  rows={7}
                  required
                />
              </label>
              <button type="submit" className="story-submit">
                <span>+</span> Add user story
              </button>
            </form>
            {error && <p className="error">{error}</p>}
          </aside>

          <section className="stories-panel">
            <div className="stories-panel-head">
              <div>
                <div className="panel-kicker">Requirements</div>
                <h2>User stories</h2>
              </div>
              <span className="filter-chip on">All {stories.length}</span>
            </div>
          {stories.length === 0 ? (
              <div className="story-empty">
                <div className="story-empty-icon">+</div>
                <h3>No user stories yet</h3>
                <p>Add your first requirement using the form on the left.</p>
              </div>
          ) : (
              <ul className="story-list">
              {stories.map((s) => (
                  <li key={s.id} className="story-row">
                    <div className="story-row-index">US</div>
                    <div className="story-row-content">
                      <Link
                        to={`/projects/${projectId}/user-stories/${s.id}`}
                        className="story-row-title"
                      >
                        {s.title}
                      </Link>
                      <p className="clamp">{s.raw_text}</p>
                      <div className="story-row-meta">
                        <span className="badge badge-blue">Ready for analysis</span>
                        <div className="story-row-actions">
                          <Link
                            to={`/projects/${projectId}/user-stories/${s.id}`}
                            className="story-open"
                          >
                            Open <span>→</span>
                          </Link>
                          <button className="danger story-delete" onClick={() => onDelete(s.id)}>
                            Delete
                          </button>
                        </div>
                      </div>
                    </div>
                  </li>
              ))}
            </ul>
          )}
          </section>
        </div>
      </div>
    </div>
  );
}
