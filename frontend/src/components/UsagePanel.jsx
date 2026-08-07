import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "../api/client";

// "This session" = since the tab was first opened (sessionStorage clears on close).
function sessionSince() {
  let s = sessionStorage.getItem("matf_session_start");
  if (!s) {
    s = new Date().toISOString();
    sessionStorage.setItem("matf_session_start", s);
  }
  return s;
}

function resetsIn(iso) {
  if (!iso) return null;
  const ms = new Date(iso).getTime() - Date.now();
  if (ms <= 0) return "now";
  const h = Math.floor(ms / 3_600_000);
  const m = Math.floor((ms % 3_600_000) / 60_000);
  return h > 0 ? `${h}h ${m}m` : `${m}m`;
}

function fmt(n) {
  return n == null ? "—" : n.toLocaleString();
}

// Circular gauge showing the fraction of today's quota still available.
function Gauge({ pct, tone }) {
  const R = 30;
  const C = 2 * Math.PI * R;
  const off = C * (1 - Math.max(0, Math.min(100, pct)) / 100);
  return (
    <svg className="ugauge" width="76" height="76" viewBox="0 0 76 76" aria-hidden>
      <circle className="ugauge-track" cx="38" cy="38" r={R} fill="none" strokeWidth="8" />
      <circle
        className={`ugauge-arc ${tone}`}
        cx="38"
        cy="38"
        r={R}
        fill="none"
        strokeWidth="8"
        strokeLinecap="round"
        strokeDasharray={C}
        strokeDashoffset={off}
        transform="rotate(-90 38 38)"
      />
      <text className="ugauge-pct" x="38" y="39" textAnchor="middle" dominantBaseline="middle">
        {Math.round(pct)}%
      </text>
    </svg>
  );
}

export default function UsagePanel({ refreshKey = 0, providerFilter = null }) {
  const [data, setData] = useState(null);
  const [err, setErr] = useState(false);
  const sinceRef = useRef(sessionSince());

  const load = useCallback(() => {
    api
      .usage(sinceRef.current)
      .then((d) => {
        setData(d);
        setErr(false);
      })
      .catch(() => setErr(true));
  }, []);

  useEffect(() => {
    load();
    const id = setInterval(load, 15_000);
    const onFocus = () => load();
    const onUsage = () => load();
    window.addEventListener("focus", onFocus);
    window.addEventListener("matf:usage", onUsage);
    return () => {
      clearInterval(id);
      window.removeEventListener("focus", onFocus);
      window.removeEventListener("matf:usage", onUsage);
    };
  }, [load]);

  useEffect(() => {
    if (refreshKey) load();
  }, [refreshKey, load]);

  if (err || !data) return null;

  let providers = data.providers.filter((p) => p.daily_limit != null);
  if (providerFilter) providers = providers.filter((p) => p.provider === providerFilter);
  if (!providers.length) return null;

  return (
    <section className="section usage-card">
      <div className="section-head">
        <div className="usage-title">
          <span className="usage-spark" aria-hidden>
            <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
              <path d="M2 10.5 6 6l3 3 5-6" />
              <path d="M11 3h3v3" />
            </svg>
          </span>
          <h2>AI usage &amp; free quota</h2>
        </div>
        <button className="usage-refresh" onClick={load} title="Refresh now" aria-label="Refresh">
          <svg width="15" height="15" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
            <path d="M13.5 8a5.5 5.5 0 1 1-1.6-3.9" />
            <path d="M13.8 2.5V5h-2.5" />
          </svg>
        </button>
      </div>

      <div className={`usage-grid ${providers.length === 1 ? "single" : ""}`}>
        {providers.map((p) => {
          const rp = p.daily_limit ? (100 * p.remaining_today) / p.daily_limit : 0;
          const tone = rp <= 10 ? "crit" : rp <= 25 ? "warn" : "ok";
          return (
            <div className="ucard" key={p.provider}>
              <div className="ucard-top">
                <span className="uname">{p.label}</span>
                <span className={`ubadge ${p.source === "provider" ? "live" : ""}`}>
                  {p.source === "provider" ? "live" : "est."}
                </span>
              </div>

              <div className="ucard-main">
                <Gauge pct={rp} tone={tone} />
                <div className="ucard-nums">
                  <div className={`ubig ${tone}`}>{fmt(p.remaining_today)}</div>
                  <div className="usub">left of {fmt(p.daily_limit)} today</div>
                  {p.live_remaining_tokens != null && (
                    <div className="utok">{fmt(p.live_remaining_tokens)} tokens/min left</div>
                  )}
                </div>
              </div>

              <div className="ustats">
                <div className="ustat"><b>{p.session}</b><span>session</span></div>
                <div className="ustat"><b>{p.today}</b><span>today</span></div>
                <div className="ustat"><b>{p.month}</b><span>month</span></div>
              </div>

              <div className="ucard-foot">
                <svg width="13" height="13" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
                  <circle cx="8" cy="8" r="6" />
                  <path d="M8 5v3l2 1.5" />
                </svg>
                resets in {resetsIn(p.next_reset_utc)} · {p.reset_label}
              </div>
            </div>
          );
        })}
      </div>
    </section>
  );
}
