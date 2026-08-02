import { useEffect, useMemo, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import { useAuth } from "../auth/AuthContext";

const ICON_BG = [
  "var(--grad-deep-blue)",
  "#7c3aed",
  "#0ea5e9",
  "#16a34a",
  "#db2777",
  "#d97706",
];

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

  async function load() {
    setLoading(true);
    try {
      const list = await api.listProjects();
      const withCounts = await Promise.all(
        list.map(async (p) => {
          const mods = await api.listModules(p.id).catch(() => []);
          const reqCount = mods.reduce((n, m) => n + (m.requirement_count || 0), 0);
          return { ...p, moduleCount: mods.length, reqCount };
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
  const totalModules = useMemo(
    () => projects.reduce((n, p) => n + (p.moduleCount || 0), 0),
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

  return (
    <div className="content">
      <header className="page-head">
        <div>
          <h1>Projects</h1>
          <p className="sub">
            {greeting()}, {handle}. {projects.length}{" "}
            {projects.length === 1 ? "project" : "projects"} · {totalReqs}{" "}
            {totalReqs === 1 ? "requirement" : "requirements"}.
          </p>
        </div>
        <button className="btn-primary" onClick={openCreate}>
          <svg width="15" height="15" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.9" strokeLinecap="round">
            <path d="M8 3v10M3 8h10" />
          </svg>
          New project
        </button>
      </header>

      <section className="stats">
        <div className="stat">
          <div className="k">Projects</div>
          <div className="v">{projects.length}</div>
          <div className="h">Scoped to your account</div>
        </div>
        <div className="stat">
          <div className="k">Requirements</div>
          <div className="v">{totalReqs}</div>
          <div className="h">Across all modules</div>
        </div>
        <div className="stat">
          <div className="k">Modules</div>
          <div className="v">{totalModules}</div>
          <div className="h">Feature groups</div>
        </div>
      </section>

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
            {sorted.map((p, i) => (
              <Link className="pcard" key={p.id} to={`/projects/${p.id}`}>
                <div className="pcard-top">
                  <div className="ic" style={{ background: ICON_BG[i % ICON_BG.length] }}>
                    {initials(p.name)}
                  </div>
                  <div style={{ minWidth: 0 }}>
                    <div className="nm">{p.name}</div>
                    <div className="ds">{p.description || "No description"}</div>
                  </div>
                </div>
                <div className="pcard-foot">
                  <span>{p.moduleCount} {p.moduleCount === 1 ? "module" : "modules"}</span>
                  <span className="fdot" />
                  <span>{p.reqCount} {p.reqCount === 1 ? "requirement" : "requirements"}</span>
                  <span style={{ marginLeft: "auto" }}>{relTime(p.created_at)}</span>
                </div>
              </Link>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
