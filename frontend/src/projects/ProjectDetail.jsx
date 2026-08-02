import { useEffect, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "../api/client";
import { MODULE_STATUSES, PRIORITIES, label, STATUS_LABEL } from "../requirements/constants";

const STATUS_CHIP = {
  active: "chip-green",
  on_hold: "chip-amber",
  completed: "chip-accent",
  archived: "chip-grey",
};
const PRIORITY_CHIP = { high: "chip-red", medium: "chip-amber", low: "chip-grey" };

export default function ProjectDetail() {
  const { projectId } = useParams();
  const [project, setProject] = useState(null);
  const [modules, setModules] = useState([]);
  const [creating, setCreating] = useState(false);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [priority, setPriority] = useState("medium");
  const [editingId, setEditingId] = useState(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const nameRef = useRef(null);

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

  function openCreate() {
    setCreating(true);
    setTimeout(() => nameRef.current?.focus(), 0);
  }

  async function onCreate(e) {
    e.preventDefault();
    setError("");
    try {
      await api.createModule(projectId, { name, description, priority });
      setName("");
      setDescription("");
      setPriority("medium");
      setCreating(false);
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

  const totalReqs = modules.reduce((n, m) => n + (m.requirement_count || 0), 0);

  return (
    <div className="content">
      <div>
        <p className="crumb">
          <Link to="/">Home</Link>
          <span className="sep">/</span>
          <span>{project?.name}</span>
        </p>
        <header className="page-head">
          <div>
            <h1>{project?.name}</h1>
            <p className="sub">
              {project?.description ||
                "Organise the product into modules, then add requirements to each."}
            </p>
          </div>
          <button className="btn-primary" onClick={openCreate}>
            <svg width="15" height="15" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.9" strokeLinecap="round">
              <path d="M8 3v10M3 8h10" />
            </svg>
            New module
          </button>
        </header>
      </div>

      <section className="stats">
        <div className="stat">
          <div className="k">Modules</div>
          <div className="v">{modules.length}</div>
          <div className="h">Feature areas</div>
        </div>
        <div className="stat">
          <div className="k">Requirements</div>
          <div className="v">{totalReqs}</div>
          <div className="h">Across all modules</div>
        </div>
        <div className="stat">
          <div className="k">Active</div>
          <div className="v">{modules.filter((m) => m.status === "active").length}</div>
          <div className="h">In progress now</div>
        </div>
      </section>

      {error && <p className="error">{error}</p>}

      {creating && (
        <form className="create-card" onSubmit={onCreate}>
          <div className="row">
            <input
              ref={nameRef}
              placeholder="Module name — e.g. Authentication"
              value={name}
              onChange={(e) => setName(e.target.value)}
              required
            />
            <select
              value={priority}
              onChange={(e) => setPriority(e.target.value)}
              style={{ maxWidth: 160 }}
            >
              {PRIORITIES.map((p) => (
                <option key={p} value={p}>priority: {p}</option>
              ))}
            </select>
          </div>
          <textarea
            placeholder="What this module covers (optional)…"
            value={description}
            rows={2}
            onChange={(e) => setDescription(e.target.value)}
          />
          <div className="actions">
            <button type="submit">Add module</button>
            <button type="button" className="ghost" onClick={() => setCreating(false)}>
              Cancel
            </button>
          </div>
        </form>
      )}

      <section>
        <div className="projects-head">
          <h2>Modules</h2>
          <span className="count">{modules.length} total</span>
        </div>

        {modules.length === 0 ? (
          <div className="empty">
            <h3>No modules yet</h3>
            <p>Group the product into feature areas, then add requirements to each.</p>
            <button className="btn-primary" onClick={openCreate} style={{ margin: "0 auto" }}>
              <svg width="15" height="15" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.9" strokeLinecap="round">
                <path d="M8 3v10M3 8h10" />
              </svg>
              New module
            </button>
          </div>
        ) : (
          <div className="mgrid">
            {modules.map((m) =>
              editingId === m.id ? (
                <div className="mcard" key={m.id}>
                  <ModuleEditRow
                    module={m}
                    onCancel={() => setEditingId(null)}
                    onSave={async (patch) => {
                      await onPatch(m.id, patch);
                      setEditingId(null);
                    }}
                  />
                </div>
              ) : (
                <div className="mcard" key={m.id}>
                  <div className="mcard-top">
                    <div className="ic">
                      <svg width="17" height="17" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
                        <rect x="2" y="2" width="5" height="5" rx="1" />
                        <rect x="9" y="2" width="5" height="5" rx="1" />
                        <rect x="2" y="9" width="5" height="5" rx="1" />
                        <rect x="9" y="9" width="5" height="5" rx="1" />
                      </svg>
                    </div>
                    <div style={{ minWidth: 0 }}>
                      <Link
                        to={`/projects/${projectId}/modules/${m.id}`}
                        className="nm"
                      >
                        {m.name}
                      </Link>
                    </div>
                  </div>
                  {m.description && <div className="ds">{m.description}</div>}
                  <div className="mcard-chips">
                    <span className={`chip ${STATUS_CHIP[m.status] || "chip-grey"}`}>
                      <span className="cdot" />
                      {label(STATUS_LABEL, m.status)}
                    </span>
                    <span className={`chip ${PRIORITY_CHIP[m.priority] || "chip-grey"}`}>
                      {m.priority}
                    </span>
                    <span className="chip chip-accent">
                      {m.requirement_count}{" "}
                      {m.requirement_count === 1 ? "req" : "reqs"}
                    </span>
                  </div>
                  <div className="mcard-foot">
                    <Link
                      to={`/projects/${projectId}/modules/${m.id}`}
                      className="mcard-open"
                    >
                      Open <span>→</span>
                    </Link>
                    <div className="mcard-acts">
                      <button className="ghost btn-sm" onClick={() => setEditingId(m.id)}>
                        Edit
                      </button>
                      <button className="danger btn-sm" onClick={() => onDelete(m.id)}>
                        Delete
                      </button>
                    </div>
                  </div>
                </div>
              )
            )}
          </div>
        )}
      </section>
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
      className="edit-form"
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
      <div className="two">
        <select value={status} onChange={(e) => setStatus(e.target.value)}>
          {MODULE_STATUSES.map((s) => (
            <option key={s} value={s}>{label(STATUS_LABEL, s)}</option>
          ))}
        </select>
        <select value={priority} onChange={(e) => setPriority(e.target.value)}>
          {PRIORITIES.map((p) => (
            <option key={p} value={p}>priority: {p}</option>
          ))}
        </select>
      </div>
      <div className="acts">
        <button type="submit" className="btn-sm">Save</button>
        <button type="button" className="ghost btn-sm" onClick={onCancel}>Cancel</button>
      </div>
    </form>
  );
}
