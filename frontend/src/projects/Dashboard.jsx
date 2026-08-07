import { useEffect, useMemo, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import UsagePanel from "../components/UsagePanel";

const ICON_BG = [
  "var(--grad-deep-blue)",
  "#7c3aed",
  "#0ea5e9",
  "#16a34a",
  "#db2777",
  "#d97706",
];

const IconPencil = () => (
  <svg width="15" height="15" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
    <path d="M11.5 2.2l2.3 2.3-8 8-3 .7.7-3z" />
    <path d="M10.5 3.2l2.3 2.3" />
  </svg>
);
const IconTrash = () => (
  <svg width="15" height="15" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
    <path d="M2.8 4.2h10.4M6 4.2V2.9h4v1.3M5 4.2l.5 9h5l.5-9" />
    <path d="M6.7 6.6v4.2M9.3 6.6v4.2" />
  </svg>
);
const IconChevron = () => (
  <svg className="chevi" width="15" height="15" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
    <path d="M10 4l-4 4 4 4" />
  </svg>
);

function initials(name) {
  const parts = (name || "").trim().split(/\s+/).filter(Boolean);
  if (parts.length >= 2) return (parts[0][0] + parts[1][0]).toUpperCase();
  return (name || "?").slice(0, 2).toUpperCase();
}

function relTime(iso) {
  if (!iso) return "—";
  const then = new Date(iso.endsWith("Z") || iso.includes("+") ? iso : iso + "Z");
  const t = then.getTime();
  if (Number.isNaN(t)) return "—";
  const m = Math.round((Date.now() - t) / 60000);
  if (m < 1) return "just now";
  if (m < 60) return `${m}m ago`;
  const h = Math.round(m / 60);
  if (h < 24) return `${h}h ago`;
  const d = Math.round(h / 24);
  if (d === 1) return "yesterday";
  if (d < 30) return `${d}d ago`;
  return then.toLocaleDateString();
}

function greeting() {
  const h = new Date().getHours();
  if (h < 12) return "Good morning";
  if (h < 18) return "Good afternoon";
  return "Good evening";
}

export default function Dashboard() {
  const { user } = useAuth();
  const [projects, setProjects] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [creating, setCreating] = useState(false);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const nameRef = useRef(null);

  // per-card edit / expandable actions
  const [editingId, setEditingId] = useState(null);
  const [openMenuId, setOpenMenuId] = useState(null);
  const [eName, setEName] = useState("");
  const [eDesc, setEDesc] = useState("");

  // headline "AI calls today" for the hero (real providers only)
  const [callsToday, setCallsToday] = useState(null);
  useEffect(() => {
    const loadUsage = () =>
      api
        .usage()
        .then((d) =>
          setCallsToday(
            (d.providers || [])
              .filter((p) => p.daily_limit != null)
              .reduce((n, p) => n + (p.today || 0), 0)
          )
        )
        .catch(() => {});
    loadUsage();
    window.addEventListener("matf:usage", loadUsage);
    return () => window.removeEventListener("matf:usage", loadUsage);
  }, []);

  async function load() {
    setLoading(true);
    try {
      const list = await api.listProjects();
      const withCounts = await Promise.all(
        list.map(async (p) => {
          const reqs = await api.listRequirements(p.id).catch(() => []);
          return { ...p, reqCount: reqs.length };
        })
      );
      setProjects(withCounts);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, []);

  const totalReqs = useMemo(
    () => projects.reduce((n, p) => n + (p.reqCount || 0), 0),
    [projects]
  );

  const sorted = useMemo(
    () =>
      [...projects].sort(
        (a, b) => new Date(b.created_at || 0) - new Date(a.created_at || 0)
      ),
    [projects]
  );

  const handle = (user?.email || "researcher").split("@")[0];

  function openCreate() {
    setCreating(true);
    setTimeout(() => nameRef.current?.focus(), 0);
  }

  async function onCreate(e) {
    e.preventDefault();
    setError("");
    try {
      await api.createProject(name, description);
      setName("");
      setDescription("");
      setCreating(false);
      await load();
    } catch (err) {
      setError(err.message);
    }
  }

  function openEdit(p, e) {
    e.preventDefault();
    setEName(p.name);
    setEDesc(p.description || "");
    setEditingId(p.id);
  }

  async function onSaveEdit(e) {
    e.preventDefault();
    setError("");
    try {
      await api.updateProject(editingId, { name: eName, description: eDesc });
      setEditingId(null);
      await load();
    } catch (err) {
      setError(err.message);
    }
  }

  async function onDeleteProject(p, e) {
    e.preventDefault();
    if (
      !confirm(
        `Delete “${p.name}”? All its requirements and generated test artifacts will be permanently removed.`
      )
    )
      return;
    try {
      await api.deleteProject(p.id);
      await load();
    } catch (err) {
      setError(err.message);
    }
  }

  return (
    <div className="content dash">
      <section className="dash-hero">
        <div className="hero-main">
          <p className="hero-eyebrow">{greeting()}, {handle}</p>
          <h1>Your test-design workspace</h1>
          <p className="hero-sub">
            Turn requirements into validated, traceable test suites with a team of
            specialized AI agents — analyze, generate, debate, and score.
          </p>
          <div className="hero-stats">
            <div className="hero-stat">
              <b>{projects.length}</b>
              <span>{projects.length === 1 ? "Project" : "Projects"}</span>
            </div>
            <div className="hero-stat">
              <b>{totalReqs}</b>
              <span>{totalReqs === 1 ? "Requirement" : "Requirements"}</span>
            </div>
            <div className="hero-stat">
              <b>{callsToday == null ? "—" : callsToday}</b>
              <span>AI calls today</span>
            </div>
          </div>
        </div>
        <button className="hero-cta" onClick={openCreate}>
          <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
            <path d="M8 3v10M3 8h10" />
          </svg>
          New project
        </button>
      </section>

      <UsagePanel />

      {error && <p className="error">{error}</p>}

      {creating && (
        <form className="create-card" onSubmit={onCreate}>
          <div className="row">
            <input
              ref={nameRef}
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
          </div>
          <div className="actions">
            <button type="submit">Create project</button>
            <button type="button" className="ghost" onClick={() => setCreating(false)}>
              Cancel
            </button>
          </div>
        </form>
      )}

      <section>
        <div className="projects-head">
          <h2>Your projects</h2>
          <span className="count">
            {loading ? "" : `${projects.length} total`}
          </span>
        </div>

        {loading ? (
          <p className="muted" style={{ padding: "8px 0" }}>
            Loading…
          </p>
        ) : projects.length === 0 ? (
          <div className="empty">
            <h3>No projects yet</h3>
            <p>Create your first project to start turning requirements into test cases.</p>
            <button className="btn-primary" onClick={openCreate} style={{ margin: "0 auto" }}>
              <svg width="15" height="15" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.9" strokeLinecap="round">
                <path d="M8 3v10M3 8h10" />
              </svg>
              New project
            </button>
          </div>
        ) : (
          <div className="pgrid">
            {sorted.map((p, i) =>
              editingId === p.id ? (
                <form className="pcard" key={p.id} onSubmit={onSaveEdit}>
                  <input
                    value={eName}
                    onChange={(e) => setEName(e.target.value)}
                    placeholder="Project name"
                    required
                    autoFocus
                  />
                  <input
                    value={eDesc}
                    onChange={(e) => setEDesc(e.target.value)}
                    placeholder="Description (optional)"
                  />
                  <div className="pcard-acts">
                    <button type="submit" className="btn-sm">Save</button>
                    <button
                      type="button"
                      className="ghost btn-sm"
                      onClick={() => setEditingId(null)}
                    >
                      Cancel
                    </button>
                  </div>
                </form>
              ) : (
                <div className="pcard" key={p.id}>
                  <Link className="pcard-open" to={`/projects/${p.id}`}>
                    <div className="pcard-top">
                      <div className="ic" style={{ background: ICON_BG[i % ICON_BG.length] }}>
                        {initials(p.name)}
                      </div>
                      <div style={{ minWidth: 0 }}>
                        <div className="nm">{p.name}</div>
                        <div className="ds">{p.description || "No description"}</div>
                      </div>
                    </div>
                  </Link>
                  <div className="pcard-foot">
                    <span className="pcard-pill">
                      {p.reqCount} {p.reqCount === 1 ? "req" : "reqs"}
                    </span>
                    <span>{relTime(p.created_at)}</span>
                    <span className="pcard-acts" style={{ marginLeft: "auto" }}>
                      {openMenuId === p.id && (
                        <>
                          <button
                            className="icon-btn"
                            title="Edit project"
                            aria-label="Edit project"
                            onClick={(e) => openEdit(p, e)}
                          >
                            <IconPencil />
                          </button>
                          <button
                            className="icon-btn danger"
                            title="Delete project"
                            aria-label="Delete project"
                            onClick={(e) => onDeleteProject(p, e)}
                          >
                            <IconTrash />
                          </button>
                        </>
                      )}
                      <button
                        className={`icon-btn chev ${openMenuId === p.id ? "open" : ""}`}
                        title="Actions"
                        aria-label="Toggle project actions"
                        aria-expanded={openMenuId === p.id}
                        onClick={(e) => {
                          e.preventDefault();
                          setOpenMenuId(openMenuId === p.id ? null : p.id);
                        }}
                      >
                        <IconChevron />
                      </button>
                    </span>
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
