import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import UsagePanel from "../components/UsagePanel";
import HowItWorks from "../components/HowItWorks";

function greeting() {
  const h = new Date().getHours();
  if (h < 12) return "Good morning";
  if (h < 18) return "Good afternoon";
  return "Good evening";
}

// Home — the story/overview. What this is, how it works, and two doors into the
// two things you can do: build test suites (Projects) or prove them (Experiments).
export default function Dashboard() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const [projects, setProjects] = useState([]);

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

  useEffect(() => {
    (async () => {
      try {
        const list = await api.listProjects();
        const withCounts = await Promise.all(
          list.map(async (p) => {
            const reqs = await api.listRequirements(p.id).catch(() => []);
            return { ...p, reqCount: reqs.length };
          })
        );
        setProjects(withCounts);
      } catch {
        /* hero stats are best-effort */
      }
    })();
  }, []);

  const totalReqs = useMemo(
    () => projects.reduce((n, p) => n + (p.reqCount || 0), 0),
    [projects]
  );

  const handle = (user?.email || "researcher").split("@")[0];

  return (
    <div className="content dash">
      <section className="dash-hero">
        <div className="hero-main">
          <p className="hero-eyebrow">{greeting()}, {handle}</p>
          <h1>Turn requirements into proven test suites</h1>
          <p className="hero-sub">
            A team of AI agents writes your test cases — then we prove they're good
            by running them against code with planted bugs and counting the catches.
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
      </section>

      <section className="hiw-section">
        <div className="hiw-head">
          <h2>How it works</h2>
          <span className="muted">Three steps, one idea</span>
        </div>
        <HowItWorks />
      </section>

      <section className="doors">
        <button className="door" onClick={() => navigate("/projects")}>
          <span className="door-ic gen" aria-hidden>
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round">
              <circle cx="8" cy="8" r="3" /><circle cx="16" cy="8" r="3" />
              <path d="M3 20c0-2.8 2.2-5 5-5s5 2.2 5 5M13.5 15.2A5 5 0 0 1 21 20" />
            </svg>
          </span>
          <span className="door-txt">
            <b>Generate tests — Projects</b>
            <span>Start a project, add a requirement, and watch the AI team build a test suite.</span>
          </span>
          <span className="door-go" aria-hidden>→</span>
        </button>

        <button className="door proof" onClick={() => navigate("/experiments")}>
          <span className="door-ic prove" aria-hidden>
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round">
              <path d="M12 3l7 3v5c0 4.5-3 8-7 10-4-2-7-5.5-7-10V6z" /><path d="M9 12l2 2 4-4" />
            </svg>
          </span>
          <span className="door-txt">
            <b>See the proof — Experiments</b>
            <span>Run the AI team against a single-AI baseline and measure who catches more bugs.</span>
          </span>
          <span className="door-go" aria-hidden>→</span>
        </button>
      </section>

      <UsagePanel />
    </div>
  );
}
