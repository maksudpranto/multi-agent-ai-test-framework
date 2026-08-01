import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "../api/client";
import { MODULE_STATUSES, PRIORITIES, label, STATUS_LABEL } from "../requirements/constants";

export default function ProjectDetail() {
  const { projectId } = useParams();
  const [project, setProject] = useState(null);
  const [modules, setModules] = useState([]);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [priority, setPriority] = useState("medium");
  const [editingId, setEditingId] = useState(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  async function load() {
    setLoading(true);
    try {
      const [p, m] = await Promise.all([
        api.getProject(projectId),
        api.listModules(projectId),
      ]);
      setProject(p);
      setModules(m);
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
      await api.createModule(projectId, { name, description, priority });
      setName("");
      setDescription("");
      setPriority("medium");
      await load();
    } catch (err) {
      setError(err.message);
    }
  }

  async function onPatch(moduleId, patch) {
    try {
      await api.updateModule(projectId, moduleId, patch);
      await load();
    } catch (err) {
      setError(err.message);
    }
  }

  async function onDelete(id) {
    if (!confirm("Delete this module? Its requirements are kept but unassigned."))
      return;
    await api.deleteModule(projectId, id);
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
            <p>{project?.description || "Organise the product into modules, then add requirements to each."}</p>
          </div>
          <div className="story-count">
            <strong>{modules.length}</strong>
            <span>{modules.length === 1 ? "module" : "modules"}</span>
          </div>
        </header>

        <div className="stories-workspace">
          <aside className="story-composer">
            <div className="panel-kicker">New module</div>
            <h2>Add a module</h2>
            <p className="muted">A feature or functional area within this project.</p>
            <form className="story-form" onSubmit={onCreate}>
              <label>
                Module name
                <input
                  placeholder="e.g. Authentication"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  required
                />
              </label>
              <label>
                Description
                <textarea
                  placeholder="What this module covers…"
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  rows={4}
                />
              </label>
              <label>
                Priority
                <select value={priority} onChange={(e) => setPriority(e.target.value)}>
                  {PRIORITIES.map((p) => (
                    <option key={p} value={p}>{p}</option>
                  ))}
                </select>
              </label>
              <button type="submit" className="story-submit">
                <span>+</span> Add module
              </button>
            </form>
            {error && <p className="error">{error}</p>}
          </aside>

          <section className="stories-panel">
            <div className="stories-panel-head">
              <div>
                <div className="panel-kicker">Modules</div>
                <h2>Feature areas</h2>
              </div>
              <span className="filter-chip on">All {modules.length}</span>
            </div>
            {modules.length === 0 ? (
              <div className="story-empty">
                <div className="story-empty-icon">+</div>
                <h3>No modules yet</h3>
                <p>Add your first module using the form on the left.</p>
              </div>
            ) : (
              <ul className="story-list">
                {modules.map((m) => (
                  <li key={m.id} className="story-row">
                    <div className="story-row-index">M</div>
                    <div className="story-row-content">
                      {editingId === m.id ? (
                        <ModuleEditRow
                          module={m}
                          onCancel={() => setEditingId(null)}
                          onSave={async (patch) => {
                            await onPatch(m.id, patch);
                            setEditingId(null);
                          }}
                        />
                      ) : (
                        <>
                          <Link
                            to={`/projects/${projectId}/modules/${m.id}`}
                            className="story-row-title"
                          >
                            {m.name}
                          </Link>
                          {m.description && <p className="clamp">{m.description}</p>}
                          <div className="story-row-meta">
                            <span className={`badge status-${m.status}`}>
                              {label(STATUS_LABEL, m.status)}
                            </span>
                            <span className="badge badge-grey">priority: {m.priority}</span>
                            <span className="badge badge-blue">
                              {m.requirement_count}{" "}
                              {m.requirement_count === 1 ? "requirement" : "requirements"}
                            </span>
                            <div className="story-row-actions">
                              <Link
                                to={`/projects/${projectId}/modules/${m.id}`}
                                className="story-open"
                              >
                                Open <span>→</span>
                              </Link>
                              <button className="ghost" onClick={() => setEditingId(m.id)}>
                                Edit
                              </button>
                              <button className="danger story-delete" onClick={() => onDelete(m.id)}>
                                Delete
                              </button>
                            </div>
                          </div>
                        </>
                      )}
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

function ModuleEditRow({ module, onSave, onCancel }) {
  const [name, setName] = useState(module.name);
  const [description, setDescription] = useState(module.description || "");
  const [status, setStatus] = useState(module.status);
  const [priority, setPriority] = useState(module.priority);
  return (
    <form
      className="inline-edit"
      onSubmit={(e) => {
        e.preventDefault();
        onSave({ name, description, status, priority });
      }}
    >
      <input value={name} onChange={(e) => setName(e.target.value)} required />
      <textarea
        value={description}
        rows={2}
        placeholder="Description"
        onChange={(e) => setDescription(e.target.value)}
      />
      <div className="inline-edit-row">
        <select value={status} onChange={(e) => setStatus(e.target.value)}>
          {MODULE_STATUSES.map((s) => (
            <option key={s} value={s}>{label(STATUS_LABEL, s)}</option>
          ))}
        </select>
        <select value={priority} onChange={(e) => setPriority(e.target.value)}>
          {PRIORITIES.map((p) => (
            <option key={p} value={p}>{p}</option>
          ))}
        </select>
        <button type="submit">Save</button>
        <button type="button" className="ghost" onClick={onCancel}>Cancel</button>
      </div>
    </form>
  );
}
