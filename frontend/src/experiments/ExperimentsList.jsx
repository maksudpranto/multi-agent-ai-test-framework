import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api/client";
import ModelPicker from "../components/ModelPicker";
import UsagePanel from "../components/UsagePanel";

const STATUS_CHIP = {
  pending: "chip-grey",
  running: "chip-amber",
  completed: "chip-green",
  failed: "chip-red",
  cancelled: "chip-grey",
};

const PAGE_SIZE = 6;

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
  return then.toLocaleDateString();
}

const IconPlay = () => (
  <svg width="14" height="14" viewBox="0 0 16 16" fill="currentColor"><path d="M4.5 3.2v9.6l8-4.8z" /></svg>
);
const IconStop = () => (
  <svg width="15" height="15" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.4">
    <circle cx="8" cy="8" r="6.5" /><rect x="5.5" y="5.5" width="5" height="5" rx="1" fill="currentColor" stroke="none" />
  </svg>
);
const IconEdit = () => (
  <svg width="15" height="15" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
    <path d="M11.5 2.2l2.3 2.3-8 8-3 .7.7-3z" /><path d="M10.5 3.2l2.3 2.3" />
  </svg>
);
const IconTrash = () => (
  <svg width="15" height="15" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
    <path d="M2.8 4.2h10.4M6 4.2V2.9h4v1.3M5 4.2l.5 9h5l.5-9" /><path d="M6.7 6.6v4.2M9.3 6.6v4.2" />
  </svg>
);

// One experiment row: status chip + live progress (with %) while it runs, plus
// run/resume/re-run, stop, rename, and delete controls (delete uses an inline
// confirm rather than a native dialog).
function ExperimentRow({ exp, onChanged }) {
  const navigate = useNavigate();
  const [live, setLive] = useState(exp);
  const [editing, setEditing] = useState(false);
  const [editName, setEditName] = useState(exp.name);
  const [confirm, setConfirm] = useState(null); // {label, action}
  const [busy, setBusy] = useState(false);

  useEffect(() => setLive(exp), [exp]);

  useEffect(() => {
    if (live.status !== "running") return undefined;
    const id = setInterval(async () => {
      try {
        const s = await api.getExperiment(live.id);
        setLive({ ...s.experiment, progress: s.progress });
      } catch {
        /* keep last known */
      }
    }, 2500);
    return () => clearInterval(id);
  }, [live.status, live.id]);

  const prog = live.progress;
  const pct = prog ? prog.pct : live.status === "completed" ? 100 : 0;
  const isRunning = live.status === "running";

  async function act(fn) {
    setBusy(true);
    try {
      await fn();
      onChanged?.();
    } catch (err) {
      alert(err.message);
    } finally {
      setBusy(false);
      setConfirm(null);
    }
  }

  async function onSaveName(e) {
    e.preventDefault();
    e.stopPropagation();
    const name = editName.trim();
    if (!name) return;
    await act(() => api.renameExperiment(live.id, name));
    setEditing(false);
  }

  function stop(e, fn) {
    e.preventDefault();
    e.stopPropagation();
    fn();
  }

  // Run / Resume / Re-run depending on status.
  const runInfo = isRunning
    ? null
    : live.status === "completed"
      ? { label: "Re-run", fresh: true, confirm: "Re-run? (clears results)" }
      : live.status === "pending"
        ? { label: "Run", fresh: false }
        : { label: "Resume", fresh: false }; // cancelled / failed

  function doRun() {
    if (runInfo.confirm) {
      setConfirm({ label: runInfo.confirm, action: () => act(() => api.runExperiment(live.id, runInfo.fresh)) });
    } else {
      act(() => api.runExperiment(live.id, runInfo.fresh));
    }
  }

  if (editing) {
    return (
      <form className="exp-row editing" onSubmit={onSaveName}>
        <input
          className="exp-rename-input"
          value={editName}
          onChange={(e) => setEditName(e.target.value)}
          autoFocus
          onClick={(e) => e.stopPropagation()}
        />
        <div className="exp-row-acts">
          <button type="submit" className="btn-sm" disabled={busy}>Save</button>
          <button type="button" className="ghost btn-sm" onClick={() => { setEditing(false); setEditName(live.name); }}>Cancel</button>
        </div>
      </form>
    );
  }

  return (
    <div className="exp-row" role="button" tabIndex={0} onClick={() => navigate(`/experiments/${live.id}`)}>
      <div className="exp-row-main">
        <div className="exp-row-name">{live.name}</div>
        <div className="exp-row-meta">
          {live.conditions.length} conditions
          {live.repetitions > 1 ? ` · ${live.repetitions} runs` : ""} · created {relTime(live.created_at)}
        </div>
      </div>

      <div className="exp-row-prog">
        {isRunning && prog && (
          <>
            <div className="exp-bar" title={`${prog.completed} / ${prog.total} cells`}>
              <span style={{ width: `${pct}%` }} />
            </div>
            <span className="exp-prog-pct">{Math.round(pct)}%</span>
          </>
        )}
      </div>

      <span className={`chip ${STATUS_CHIP[live.status] || "chip-grey"}`}>
        {isRunning && <span className="spinner sm" />}
        {live.status}
      </span>

      <div className="exp-row-acts" onClick={(e) => e.stopPropagation()}>
        {confirm ? (
          <span className="row-confirm">
            <span className="row-confirm-txt">{confirm.label}</span>
            <button className="btn-sm solid-danger" disabled={busy} onClick={(e) => stop(e, confirm.action)}>Yes</button>
            <button className="ghost btn-sm" onClick={(e) => stop(e, () => setConfirm(null))}>No</button>
          </span>
        ) : (
          <>
            {runInfo && (
              <button className="icon-btn" title={runInfo.label} aria-label={runInfo.label} disabled={busy}
                onClick={(e) => stop(e, doRun)}>
                <IconPlay />
              </button>
            )}
            {isRunning && (
              <button className="icon-btn" title="Stop" aria-label="Stop experiment" disabled={busy}
                onClick={(e) => stop(e, () => act(() => api.stopExperiment(live.id)))}>
                <IconStop />
              </button>
            )}
            <button className="icon-btn" title="Rename" aria-label="Rename experiment"
              onClick={(e) => stop(e, () => { setEditName(live.name); setEditing(true); })}>
              <IconEdit />
            </button>
            <button className="icon-btn danger" title="Delete" aria-label="Delete experiment" disabled={busy || isRunning}
              onClick={(e) => stop(e, () => setConfirm({ label: "Delete?", action: () => act(() => api.deleteExperiment(live.id)) }))}>
              <IconTrash />
            </button>
          </>
        )}
      </div>
    </div>
  );
}

export default function ExperimentsList() {
  const navigate = useNavigate();
  const [conditions, setConditions] = useState([]);
  const [experiments, setExperiments] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  // Setup / seed state
  const [seed, setSeed] = useState(null);
  const [seeding, setSeeding] = useState(false);

  // Create form
  const [name, setName] = useState("");
  const [picked, setPicked] = useState({});
  const [reps, setReps] = useState(1);
  const [launching, setLaunching] = useState(false);
  const [selectedProvider, setSelectedProvider] = useState(null);
  const nameRef = useRef(null);

  // List: search + pagination
  const [query, setQuery] = useState("");
  const [page, setPage] = useState(0);

  const load = useCallback(async () => {
    try {
      const [conds, exps] = await Promise.all([
        api.listConditions(),
        api.listExperiments(),
      ]);
      setConditions(conds);
      setExperiments(exps);
      setPicked((prev) =>
        Object.keys(prev).length ? prev : Object.fromEntries(conds.map((c) => [c.key, true]))
      );
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    return q ? experiments.filter((e) => e.name.toLowerCase().includes(q)) : experiments;
  }, [experiments, query]);

  const pageCount = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE));
  const safePage = Math.min(page, pageCount - 1);
  const pageItems = filtered.slice(safePage * PAGE_SIZE, (safePage + 1) * PAGE_SIZE);

  useEffect(() => {
    setPage(0);
  }, [query]);

  async function onSeed() {
    setSeeding(true);
    setError("");
    try {
      const info = await api.seedBenchmark();
      setSeed(info);
    } catch (err) {
      setError(err.message);
    } finally {
      setSeeding(false);
    }
  }

  async function onLaunch(e) {
    e.preventDefault();
    setError("");
    const chosen = conditions.filter((c) => picked[c.key]).map((c) => c.key);
    if (!name.trim() || chosen.length === 0) return;
    setLaunching(true);
    try {
      const exp = await api.createExperiment({ name: name.trim(), conditions: chosen, repetitions: reps });
      await api.runExperiment(exp.id);
      navigate(`/experiments/${exp.id}`);
    } catch (err) {
      setError(err.message);
      setLaunching(false);
    }
  }

  const nSelected = conditions.filter((c) => picked[c.key]).length;

  return (
    <div className="content exp-page">
      <section className="exp-hero">
        <div>
          <p className="hero-eyebrow">Research</p>
          <h1>Experiments</h1>
          <p className="hero-sub">
            Run a controlled, fault-based comparison: each condition turns the same
            requirements into a test suite, and we <b>run those suites against code
            with seeded bugs</b> to measure how many they catch — with a significance
            test, not a guess.
          </p>
        </div>
      </section>

      {error && <p className="error">{error}</p>}

      {/* Step 1 — benchmark */}
      <section className="section exp-setup">
        <div className="section-head">
          <h2>
            <span className="step-n">1</span> Benchmark corpus
          </h2>
          <button className="ghost" onClick={onSeed} disabled={seeding}>
            {seeding ? (
              <span className="busy-label"><span className="spinner" /> Seeding…</span>
            ) : (
              "Seed / refresh benchmark"
            )}
          </button>
        </div>
        <p className="muted exp-setup-copy">
          Eight everyday features — ATM withdrawal, login lockout, sign-up validation,
          bank transfer and more — each with a plain-language requirement, a reference
          implementation, and four deliberately planted bugs. Seeding is safe to
          re-run — it never duplicates anything.
        </p>
        {seed && (
          <div className="exp-seed-note">
            ✓ Benchmark ready — {seed.n_items} programs
            {seed.created ? ` (${seed.created} added)` : ""}
            {seed.refreshed ? ` (${seed.refreshed} refreshed)` : ""}.
          </div>
        )}
      </section>

      {/* Step 2 — configure + run */}
      <section className="section">
        <div className="section-head">
          <h2>
            <span className="step-n">2</span> New experiment
          </h2>
        </div>
        <form className="exp-create" onSubmit={onLaunch}>
          <label className="field">
            <span className="field-label">Name</span>
            <input
              ref={nameRef}
              placeholder="e.g. Multi-agent vs baseline — run 1"
              value={name}
              onChange={(e) => setName(e.target.value)}
              required
            />
          </label>

          <div className="field">
            <span className="field-label">Conditions to compare</span>
            <div className="cond-pills">
              {conditions.map((c) => (
                <label
                  key={c.key}
                  className={`cond-pill ${picked[c.key] ? "on" : ""} ${c.is_baseline ? "base" : ""}`}
                  title={c.description}
                >
                  <input
                    type="checkbox"
                    checked={!!picked[c.key]}
                    onChange={(e) => setPicked((p) => ({ ...p, [c.key]: e.target.checked }))}
                  />
                  <span className="cp-label">{c.label}</span>
                  {c.is_baseline && <span className="cp-tag">baseline</span>}
                </label>
              ))}
            </div>
          </div>

          <div className="field">
            <span className="field-label">
              Repeat runs
              <span className="field-hint"> — AI output varies run to run; repeating averages out the noise and reports the spread</span>
            </span>
            <div className="reps-pills">
              {[1, 3, 5].map((n) => (
                <button
                  type="button"
                  key={n}
                  className={`reps-pill ${reps === n ? "on" : ""}`}
                  onClick={() => setReps(n)}
                >
                  {n === 1 ? "1 run" : `${n} runs`}
                </button>
              ))}
            </div>
          </div>

          <div className="exp-create-foot">
            <ModelPicker onProviderChange={setSelectedProvider} />
            <button type="submit" disabled={launching || !name.trim() || nSelected === 0}>
              {launching ? (
                <span className="busy-label"><span className="spinner" /> Launching…</span>
              ) : (
                "Run experiment"
              )}
            </button>
          </div>
          <p className="muted exp-hint">
            The study runs in the background across every program × condition. You can
            watch progress below and open the results the moment it finishes. On a real
            provider this spends free-tier quota; the offline mock runs for free.
          </p>
        </form>
      </section>

      {/* Live quota for the model that will run the study */}
      <UsagePanel providerFilter={selectedProvider} />

      {/* Experiments list */}
      <section className="section">
        <div className="section-head">
          <h2>Your experiments</h2>
          <div className="exp-list-tools">
            <div className="exp-search">
              <svg width="14" height="14" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round">
                <circle cx="7" cy="7" r="4.5" /><path d="M13.5 13.5 10.5 10.5" />
              </svg>
              <input
                placeholder="Search by name…"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
              />
            </div>
            <span className="count">{loading ? "" : `${filtered.length} total`}</span>
          </div>
        </div>

        {loading ? (
          <p className="muted" style={{ padding: "8px 0" }}>Loading…</p>
        ) : experiments.length === 0 ? (
          <div className="empty">
            <h3>No experiments yet</h3>
            <p>Seed the benchmark and launch your first study above.</p>
          </div>
        ) : filtered.length === 0 ? (
          <div className="empty">
            <h3>No matches</h3>
            <p>No experiments match “{query}”.</p>
          </div>
        ) : (
          <>
            <div className="exp-list">
              {pageItems.map((exp) => (
                <ExperimentRow key={exp.id} exp={exp} onChanged={load} />
              ))}
            </div>
            {pageCount > 1 && (
              <div className="exp-pager">
                <button className="ghost btn-sm" disabled={safePage === 0} onClick={() => setPage(safePage - 1)}>
                  ← Prev
                </button>
                <span className="exp-pager-info">Page {safePage + 1} of {pageCount}</span>
                <button className="ghost btn-sm" disabled={safePage >= pageCount - 1} onClick={() => setPage(safePage + 1)}>
                  Next →
                </button>
              </div>
            )}
          </>
        )}
      </section>
    </div>
  );
}
