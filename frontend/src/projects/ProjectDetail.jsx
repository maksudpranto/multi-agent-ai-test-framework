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
    <div className="content">
      <div className="page">
        <p className="breadcrumb">
          <Link to="/">Home</Link> / {project?.name}
        </p>
        <h1>{project?.name}</h1>
        {project?.description && <p className="muted">{project.description}</p>}

        <section className="section">
          <h2>Add user story</h2>
          <form className="stacked-form" onSubmit={onCreate}>
            <input
              placeholder="Story title"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              required
            />
            <textarea
              placeholder="As a user, I want to… so that…"
              value={rawText}
              onChange={(e) => setRawText(e.target.value)}
              rows={4}
              required
            />
            <button type="submit">Add user story</button>
          </form>
          {error && <p className="error">{error}</p>}
        </section>

        <section className="section">
          <div className="section-head">
            <h2>User stories</h2>
            <span className="muted">{stories.length} total</span>
          </div>
          {stories.length === 0 ? (
            <p className="muted">No user stories yet. Add one above.</p>
          ) : (
            <ul className="card-list" style={{ marginTop: 16 }}>
              {stories.map((s) => (
                <li key={s.id} className="list-card">
                  <div style={{ minWidth: 0 }}>
                    <Link
                      to={`/projects/${projectId}/user-stories/${s.id}`}
                      className="list-title"
                    >
                      {s.title}
                    </Link>
                    <p className="muted clamp">{s.raw_text}</p>
                  </div>
                  <button className="danger" onClick={() => onDelete(s.id)}>
                    Delete
                  </button>
                </li>
              ))}
            </ul>
          )}
        </section>
      </div>
    </div>
  );
}
