import { useEffect, useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import { api } from "../api/client";

// Inline 16px stroke icons — no icon dependency.
const icons = {
  home: (
    <svg width="17" height="17" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <path d="M2 6.5 8 2l6 4.5V13a1 1 0 0 1-1 1H3a1 1 0 0 1-1-1z" />
      <path d="M6.2 14V9h3.6v5" />
    </svg>
  ),
  projects: (
    <svg width="17" height="17" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <path d="M1.8 4.3A1.2 1.2 0 0 1 3 3.1h2.9l1.3 1.7h5A1.2 1.2 0 0 1 13.4 6v6.2a1.2 1.2 0 0 1-1.2 1.2H3a1.2 1.2 0 0 1-1.2-1.2z" />
    </svg>
  ),
  logout: (
    <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <path d="M6 2.5H3.5a1 1 0 0 0-1 1v9a1 1 0 0 0 1 1H6" />
      <path d="M10.5 11 13.5 8 10.5 5M13.2 8H6.2" />
    </svg>
  ),
};

export default function AppShell({ children }) {
  const { user, logout } = useAuth();
  const { pathname } = useLocation();
  const navigate = useNavigate();

  const email = user?.email || "";
  const handle = email.split("@")[0] || "researcher";
  const initials =
    handle
      .split(/[.\-_]/)
      .map((p) => p[0])
      .filter(Boolean)
      .slice(0, 2)
      .join("")
      .toUpperCase() || "U";

  function onLogout() {
    logout();
    navigate("/login");
  }

  const atHome = pathname === "/";
  const inProject = pathname.startsWith("/projects");

  const [llm, setLlm] = useState(null);
  useEffect(() => {
    api.llmMeta().then(setLlm).catch(() => setLlm(null));
  }, []);

  const llmState = !llm
    ? null
    : llm.is_mock
    ? { cls: "warn", dot: "warn", text: "Offline stub (mock)", sub: "Not real AI" }
    : llm.key_missing
    ? { cls: "warn", dot: "warn", text: llm.provider_label, sub: "API key missing" }
    : { cls: "ok", dot: "ok", text: llm.provider_label, sub: llm.model };

  return (
    <div className="app">
      <aside className="side">
        <Link to="/" className="side-brand">
          <div className="mark">M</div>
          <div>
            <div className="nm">MATF</div>
            <div className="sb">Test Framework</div>
          </div>
        </Link>

        <div className="side-label">Workspace</div>
        <nav className="side-nav">
          <Link to="/" className={`${atHome ? "active" : ""}`}>
            {icons.home}
            Home
          </Link>
          <Link to="/" className={`${inProject ? "active" : ""}`}>
            {icons.projects}
            Projects
          </Link>
        </nav>

        {llmState && (
          <div className={`llm-badge ${llmState.cls}`} title={`AI backend: ${llmState.text} · ${llmState.sub}`}>
            <span className={`llm-dot ${llmState.dot}`} />
            <div className="llm-meta">
              <div className="llm-t">{llmState.text}</div>
              <div className="llm-s">{llmState.sub}</div>
            </div>
          </div>
        )}

        <div className="side-user">
          <div className="avatar">{initials}</div>
          <div className="who">
            <div className="n">{handle}</div>
            <div className="e">{email}</div>
          </div>
          <button className="out" onClick={onLogout} title="Log out" aria-label="Log out">
            {icons.logout}
          </button>
        </div>
      </aside>

      <div className="main-col">{children}</div>
    </div>
  );
}
