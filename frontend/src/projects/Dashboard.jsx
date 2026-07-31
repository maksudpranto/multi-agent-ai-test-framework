import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api/client";

export default function Dashboard() {
  const [projects, setProjects] = useState([]);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  async function load() {
    setLoading(true);
    try {
      setProjects(await api.listProjects());
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, []);

  async function onCreate(e) {
    e.preventDefault();
    setError("");
    try {
      await api.createProject(name, description);
      setName("");
      setDescription("");
      await load();
    } catch (err) {
      setError(err.message);
    }
  }

  async function onDelete(id) {
    if (!confirm("Delete this project and all its user stories?")) return;
    await api.deleteProject(id);
    await load();
  }

  return (
    <div className="page">
      <h1>Projects</h1>

      <form className="inline-form" onSubmit={onCreate}>
        <input
          placeholder="Project name"
          value={name}
          onChange={(e) => setName(e.target.value)}
          required
        />
        <input
          placeholder="Description (optional)"
          value={description}
          onChange={(e) => setDescription(e.target.value)}
        />
        <button type="submit">Create Project</button>
      </form>

      {error && <p className="error">{error}</p>}

      {loading ? (
        <p className="muted">Loading…</p>
      ) : projects.length === 0 ? (
        <p className="muted">No projects yet. Create your first one above.</p>
      ) : (
        <ul className="card-list">
          {projects.map((p) => (
            <li key={p.id} className="card">
              <div>
                <Link to={`/projects/${p.id}`} className="card-title">
                  {p.name}
                </Link>
                {p.description && <p className="muted">{p.description}</p>}
              </div>
              <button className="danger" onClick={() => onDelete(p.id)}>
                Delete
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
