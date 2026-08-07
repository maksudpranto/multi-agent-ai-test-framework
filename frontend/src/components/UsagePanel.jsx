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
    const id = setInterval(load, 15_000); // keep counts fresh
    const onFocus = () => load();
    // Fired by the api client right after any pipeline call completes.
    const onUsage = () => load();
    window.addEventListener("focus", onFocus);
    window.addEventListener("matf:usage", onUsage);
    return () => {
      clearInterval(id);
      window.removeEventListener("focus", onFocus);
      window.removeEventListener("matf:usage", onUsage);
    };
  }, [load]);

  // Re-fetch when the parent signals a run just finished.
  useEffect(() => {
    if (refreshKey) load();
  }, [refreshKey, load]);

  if (err) return null;
  if (!data) return null;

  let providers = data.providers.filter((p) => p.daily_limit != null);
  // On the requirement page we scope the panel to the model chosen in the
  // dropdown, so usage shown matches what the next run will actually consume.
  if (providerFilter) providers = providers.filter((p) => p.provider === providerFilter);
  if (!providers.length) return null;

  return (
    <section className="section usage-card">
      <div className="section-head">
        <h2>AI usage &amp; free quota</h2>
        <button className="btn-ghost usage-refresh" onClick={load} title="Refresh now">
          ↻
        </button>
      </div>

      <div className="usage-rows">
        {providers.map((p) => {
          const pct = p.daily_limit
            ? Math.min(100, Math.round((100 * p.today) / p.daily_limit))
            : 0;
          const low = p.remaining_today != null && p.remaining_today <= Math.max(3, p.daily_limit * 0.1);
          return (
            <div className="usage-row" key={p.provider}>
              <div className="usage-top">
                <span className="usage-name">
                  {p.label}
                  {!p.ready && <span className="usage-off"> · no key</span>}
                  <span className={`usage-src ${p.source === "provider" ? "live" : ""}`}>
                    {p.source === "provider" ? "live" : "est."}
                  </span>
                </span>
                <span className={`usage-remain ${low ? "low" : ""}`}>
                  {p.remaining_today}
                  <span className="usage-of"> / {p.daily_limit} left today</span>
                </span>
              </div>
              <div className="usage-bar">
                <div
                  className={`usage-fill ${low ? "low" : ""}`}
                  style={{ width: `${pct}%` }}
                />
              </div>
              <div className="usage-meta">
                <span>session <b>{p.session}</b></span>
                <span>today <b>{p.today}</b></span>
                <span>month <b>{p.month}</b></span>
                {p.live_remaining_tokens != null && (
                  <span>tokens <b>{p.live_remaining_tokens.toLocaleString()}</b> left</span>
                )}
                <span className="usage-reset">
                  resets in {resetsIn(p.next_reset_utc)} · {p.reset_label}
                </span>
              </div>
            </div>
          );
        })}
      </div>

      <p className="usage-foot">
        <b>live</b> = real remaining reported by the provider (matches its dashboard, counts
        all usage); <b>est.</b> = our app-log count vs the published cap (Gemini exposes no
        live quota). session/today/month = calls made in this app. These are free tiers with
        no monthly limit, so “month” is usage to date.
      </p>
    </section>
  );
}
