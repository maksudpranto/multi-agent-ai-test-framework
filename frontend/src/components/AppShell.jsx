import { Link, useLocation, useNavigate } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import { PIPELINE_STAGES } from "../pipeline/stages";

// Icons kept inline (no icon dependency) — 16px stroke set from the design.
const icons = {
  home: (
    <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5">
      <rect x="1.5" y="1.5" width="5.5" height="5.5" rx="1" />
      <rect x="9" y="1.5" width="5.5" height="5.5" rx="1" />
      <rect x="1.5" y="9" width="5.5" height="5.5" rx="1" />
      <rect x="9" y="9" width="5.5" height="5.5" rx="1" />
    </svg>
  ),
  projects: (
    <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5">
      <path d="M1.5 4.2a1.2 1.2 0 0 1 1.2-1.2h3.1l1.4 1.8h5.1a1.2 1.2 0 0 1 1.2 1.2v6.3a1.2 1.2 0 0 1-1.2 1.2H2.7a1.2 1.2 0 0 1-1.2-1.2z" />
    </svg>
  ),
  stories: (
    <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5">
      <path d="M3 1.8h6.2L13 5.6v8.6H3z" />
      <path d="M9 1.8v4h4" />
      <path d="M5.4 9.2h5.2M5.4 11.6h3.4" />
    </svg>
  ),
  runs: (
    <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5">
      <circle cx="8" cy="4.4" r="2.4" />
      <circle cx="3.4" cy="11.8" r="2" />
      <circle cx="12.6" cy="11.8" r="2" />
      <path d="M6.3 5.9 4.6 10M9.7 5.9l1.7 4.1M5.4 11.8h5.2" />
    </svg>
  ),
  reports: (
    <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5">
      <path d="M2 13.5V8M6 13.5V4M10 13.5V6.5M14 13.5V2.5" />
    </svg>
  ),
  experiments: (
    <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5">
      <path d="M6 1.8v4L2.6 12a1.3 1.3 0 0 0 1.1 2h8.6a1.3 1.3 0 0 0 1.1-2L10 5.8v-4" />
      <path d="M5 1.8h6M5.4 9h5.2" />
    </svg>
  ),
  settings: (
    <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5">
      <circle cx="8" cy="8" r="2.2" />
      <path d="M8 1.5v1.8M8 12.7v1.8M14.5 8h-1.8M3.3 8H1.5M12.6 3.4l-1.3 1.3M4.7 11.3l-1.3 1.3M12.6 12.6l-1.3-1.3M4.7 4.7 3.4 3.4" />
    </svg>
  ),
};

function NavItem({ icon, label, to, active, soon }) {
  if (soon) {
    return (
      <div className="nav-item disabled" title="Arrives in a later phase">
        {icons[icon]}
        {label}
        <span className="nav-soon">Soon</span>
      </div>
    );
  }
  return (
    <Link to={to} className={`nav-item${active ? " active" : ""}`}>
      {icons[icon]}
      {label}
    </Link>
  );
}

export default function AppShell({ children }) {
  const { user, logout } = useAuth();
  const { pathname } = useLocation();
  const navigate = useNavigate();

  const liveStages = PIPELINE_STAGES.filter((s) => s.implemented).length;
  const totalStages = PIPELINE_STAGES.length;
  const pct = Math.round((liveStages / totalStages) * 100);

  const email = user?.email || "";
  const initials =
    email
      .split("@")[0]
      .split(/[.\-_]/)
      .map((p) => p[0])
      .filter(Boolean)
      .slice(0, 2)
      .join("")
      .toUpperCase() || "U";
  const handle = email.split("@")[0] || "researcher";

  function onLogout() {
    logout();
    navigate("/login");
  }

  const atHome = pathname === "/";

  return (
    <div className="shell">
      <aside className="sidebar">
        <Link to="/" className="sidebar-brand">
          <div className="brand-mark">M</div>
          <div>
            <div className="brand-name">MATF</div>
            <div className="brand-sub">Test Framework</div>
          </div>
        </Link>

        <div className="side-section">
          <div className="side-label">Workspace</div>
          <NavItem icon="home" label="Home" to="/" active={atHome} />
          <NavItem icon="projects" label="Projects" to="/" active={false} />
          <NavItem icon="stories" label="User stories" soon />
          <NavItem icon="runs" label="Pipeline runs" soon />
          <NavItem icon="reports" label="Quality reports" soon />
        </div>

        <div className="side-section">
          <div className="side-label">Research</div>
          <NavItem icon="experiments" label="Experiments" soon />
          <NavItem icon="settings" label="Prompt & agents" soon />
        </div>

        <div className="side-foot">
          <div className="side-card">
            <div className="side-card-label">Build progress</div>
            <div className="side-card-value">
              <b>{liveStages}</b>
              <span>/ {totalStages} stages live</span>
            </div>
            <div className="side-meter">
              <div style={{ width: `${pct}%` }} />
            </div>
          </div>
        </div>
      </aside>

      <main style={{ display: "flex", flexDirection: "column", minWidth: 0 }}>
        <header className="topbar">
          <div className="topbar-search">
            <svg width="15" height="15" viewBox="0 0 16 16" fill="none" stroke="var(--text-secondary)" strokeWidth="1.6">
              <circle cx="7" cy="7" r="4.6" />
              <path d="m10.4 10.4 3.1 3.1" />
            </svg>
            <span>Search projects, stories, test cases</span>
            <span className="kbd">⌘K</span>
          </div>
          <div className="topbar-right">
            <div className="status-pill">
              <span className="dot" />
              Phase 1 · Requirement Analysis live
            </div>
            <div className="topbar-divider" />
            <div className="userbox">
              <div className="avatar">{initials}</div>
              <div className="meta">
                <div className="name">{handle}</div>
                <div className="role">Researcher</div>
              </div>
            </div>
            <button className="link-btn" onClick={onLogout}>
              Log out
            </button>
          </div>
        </header>

        {children}
      </main>
    </div>
  );
}
