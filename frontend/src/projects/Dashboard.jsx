import { useEffect, useMemo, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import { useAuth } from "../auth/AuthContext";

// The reasoning agents in the pipeline. Status is driven by the real build
// state so the dashboard never overstates what exists.
const CREW = [
  { code: "RA", name: "Requirement Analysis", role: "Extracts actors, flows & acceptance criteria", live: true, color: "rgba(0,102,178,0.10)", fg: "var(--blue-700)" },
  { code: "TG", name: "Test Generation", role: "Drafts test cases from each criterion", live: false, color: "rgba(78,85,201,0.10)", fg: "var(--indigo-accent)" },
  { code: "RV", name: "Reviewer", role: "Hunts gaps, overlaps & weak assertions", live: false, color: "rgba(216,0,50,0.09)", fg: "var(--crimson)" },
  { code: "CS", name: "Consensus", role: "Debates the reviewer to resolve findings", live: false, color: "rgba(121,30,148,0.10)", fg: "var(--mauveine)" },
  { code: "CV", name: "Coverage", role: "Maps cases back to acceptance criteria", live: false, color: "rgba(0,103,163,0.10)", fg: "var(--blue-600)" },
  { code: "QA", name: "Quality Evaluation", role: "Scores clarity, atomicity & traceability", live: false, color: "rgba(123,201,80,0.14)", fg: "var(--poly-green)" },
];

// Right-hand hero card: honest readiness of the pipeline, not a fake score.
const READINESS = [
  { label: "Requirement analysis", pct: 100, color: "var(--blue-600)", note: "Live" },
  { label: "Test generation", pct: 0, color: "var(--indigo-accent)", note: "Phase 2" },
  { label: "Review & consensus", pct: 0, color: "var(--mauveine)", note: "Phase 3–4" },
  { label: "Coverage & quality", pct: 0, color: "var(--lime-green)", note: "Phase 5" },
];

const AVATAR_BG = [
  "var(--grad-deep-blue)",
  "var(--mauveine)",
  "var(--blue-600)",
  "var(--selise-globe-grey)",
  "var(--blue-800)",
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
  const diff = Date.now() - t;
  const m = Math.round(diff / 60000);
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
          const stories = await api.listUserStories(p.id).catch(() => []);
          return { ...p, storyCount: stories.length };
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

  const totalStories = useMemo(
    () => projects.reduce((n, p) => n + (p.storyCount || 0), 0),
    [projects]
  );

  const recent = useMemo(
    () =>
      [...projects]
        .sort((a, b) => new Date(b.created_at || 0) - new Date(a.created_at || 0))
        .slice(0, 4),
    [projects]
  );

  const handle = (user?.email || "researcher").split("@")[0];
  const latest = recent[0];

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
      {/* ---------- Hero ---------- */}
      <section className="hero-grid">
        <div className="hero">
          <div className="hero-inner">
            <div className="hero-eyebrow">
              {new Date().toLocaleDateString(undefined, { weekday: "long", day: "numeric", month: "long" })}
            </div>
            <h1>
              {greeting()}, {handle}.
            </h1>
            <p>
              {projects.length === 0 ? (
                <>Create your first project to start turning user stories into structured, testable specifications. <strong>Requirement Analysis</strong> is live and ready.</>
              ) : (
                <>You have <strong>{projects.length} {projects.length === 1 ? "project" : "projects"}</strong> and <strong>{totalStories} user {totalStories === 1 ? "story" : "stories"}</strong>. The <strong>Requirement Analysis</strong> agent is live — open a story to break it into actors, flows and acceptance criteria.</>
              )}
            </p>
          </div>
          <div className="hero-actions">
            <button className="btn btn-on-hero" onClick={openCreate}>
              <svg width="15" height="15" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.8">
                <path d="M8 3v10M3 8h10" />
              </svg>
              New project
            </button>
            {latest && (
              <Link className="btn btn-hero-ghost" to={`/projects/${latest.id}`}>
                Open {latest.name.length > 22 ? latest.name.slice(0, 22) + "…" : latest.name}
              </Link>
            )}
            <a className="btn btn-hero-outline" href="#projects">
              Browse projects
            </a>
          </div>
        </div>

        <div className="quality-card">
          <div className="quality-head">
            <div className="title">Pipeline readiness</div>
            <span className="tag">8-phase build</span>
          </div>
          <div className="quality-score">
            <span className="big">{Math.round((READINESS.filter((r) => r.pct === 100).length / READINESS.length) * 100)}%</span>
            <span className="sub">of the pipeline is live</span>
            <span className="delta">Phase 1</span>
          </div>
          <div className="meters">
            {READINESS.map((r) => (
              <div className="meter-row" key={r.label}>
                <div className="meter-top">
                  <span>{r.label}</span>
                  <span className="v">{r.note}</span>
                </div>
                <div className="meter">
                  <div style={{ width: `${Math.max(r.pct, 2)}%`, background: r.color, opacity: r.pct === 0 ? 0.25 : 1 }} />
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ---------- Stats ---------- */}
      <section className="stat-grid">
        <div className="stat-card">
          <div className="stat-label">Active projects</div>
          <div className="stat-value">{projects.length}</div>
          <div className="stat-sub">Scoped to your account</div>
        </div>
        <div className="stat-card">
          <div className="stat-label">User stories</div>
          <div className="stat-value">{totalStories}</div>
          <div className="stat-sub">Ready for requirement analysis</div>
        </div>
        <div className="stat-card">
          <div className="stat-label">Test cases</div>
          <div className="stat-value">0</div>
          <div className="stat-sub">Generation lands in Phase 2</div>
        </div>
        <div className="stat-card">
          <div className="stat-label">Reasoning agents</div>
          <div className="stat-value accent">{CREW.length}</div>
          <div className="stat-sub">{CREW.filter((c) => c.live).length} live · {CREW.filter((c) => !c.live).length} planned</div>
        </div>
      </section>

      {/* ---------- Projects + rail ---------- */}
      <section className="main-grid" id="projects">
        <div className="panel">
          <div className="panel-head">
            <h2>Your projects</h2>
            <span className="filter-chip on">All {projects.length}</span>
            <div className="spacer" />
            <button className="ghost" onClick={openCreate}>New project</button>
          </div>

          {error && <p className="error" style={{ padding: "12px 24px", margin: 0 }}>{error}</p>}

          {creating && (
            <form className="inline-form" style={{ padding: "16px 24px", borderBottom: "1px solid var(--divider)" }} onSubmit={onCreate}>
              <input ref={nameRef} placeholder="Project name" value={name} onChange={(e) => setName(e.target.value)} required />
              <input placeholder="Description (optional)" value={description} onChange={(e) => setDescription(e.target.value)} />
              <button type="submit">Create</button>
              <button type="button" className="ghost" onClick={() => setCreating(false)}>Cancel</button>
            </form>
          )}

          <div className="ptable-head">
            <div>Project</div>
            <div>Stories</div>
            <div>Pipeline stage</div>
            <div className="right">Quality</div>
            <div className="right">Updated</div>
          </div>

          {loading ? (
            <p className="muted" style={{ padding: "20px 24px" }}>Loading…</p>
          ) : projects.length === 0 ? (
            <p className="muted" style={{ padding: "24px" }}>
              No projects yet. Use <strong>New project</strong> to create your first one.
            </p>
          ) : (
            projects.map((p, i) => (
              <div className="ptable-row" key={p.id}>
                <div className="proj-cell">
                  <div className="avatar-sq" style={{ background: AVATAR_BG[i % AVATAR_BG.length] }}>
                    {initials(p.name)}
                  </div>
                  <div style={{ minWidth: 0 }}>
                    <div className="proj-name">
                      <Link to={`/projects/${p.id}`}>{p.name}</Link>
                    </div>
                    <div className="proj-sub">{p.description || "No description"}</div>
                  </div>
                </div>
                <div className="cell-num">
                  <b>{p.storyCount}</b> <span className="s">{p.storyCount === 1 ? "story" : "stories"}</span>
                </div>
                <div>
                  {p.storyCount > 0 ? (
                    <span className="badge badge-blue">Ready to analyze</span>
                  ) : (
                    <span className="badge badge-grey">No stories yet</span>
                  )}
                </div>
                <div className="right score-num" style={{ color: "var(--text-secondary)" }}>—</div>
                <div className="right" style={{ fontSize: 12.5, color: "var(--text-secondary)" }}>{relTime(p.created_at)}</div>
              </div>
            ))
          )}
        </div>

        <div className="rail">
          <div className="panel panel-pad">
            <div className="rail-head">
              <h2>Agent crew</h2>
              <span className="filter-chip on">{CREW.filter((c) => c.live).length}/{CREW.length} live</span>
            </div>
            <p className="rail-desc">
              Specialised agents collaborate on each story — the thesis's core claim over a single-prompt baseline.
            </p>
            <div className="crew-list">
              {CREW.map((c) => (
                <div className="crew-item" key={c.code}>
                  <div className="crew-badge" style={{ background: c.color, color: c.fg }}>{c.code}</div>
                  <div className="crew-body">
                    <div className="crew-name">{c.name}</div>
                    <div className="crew-role">{c.role}</div>
                  </div>
                  {c.live ? (
                    <span className="dot-lg" style={{ background: "var(--lime-green)" }} title="Live" />
                  ) : (
                    <span className="crew-status" style={{ color: "var(--text-secondary)" }}>planned</span>
                  )}
                </div>
              ))}
            </div>
          </div>

          <div className="panel panel-pad">
            <h2 style={{ marginBottom: 16 }}>Recent activity</h2>
            {recent.length === 0 ? (
              <p className="muted" style={{ margin: 0, fontSize: 13.5 }}>
                Nothing yet. Create a project to see activity here.
              </p>
            ) : (
              <div className="activity-list">
                {recent.map((p, i) => (
                  <div className="activity-item" key={p.id}>
                    <div className="activity-dot" style={{ background: i === 0 ? "var(--blue-600)" : "var(--selise-globe-grey)" }} />
                    <div>
                      <div className="activity-text">
                        Project <Link to={`/projects/${p.id}`}>{p.name}</Link> created
                        {p.storyCount > 0 ? ` · ${p.storyCount} ${p.storyCount === 1 ? "story" : "stories"}` : ""}.
                      </div>
                      <div className="activity-time">{relTime(p.created_at)}</div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </section>
    </div>
  );
}
