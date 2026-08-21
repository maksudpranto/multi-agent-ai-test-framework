import { useCallback, useEffect, useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api } from "../api/client";
import ModelPicker from "../components/ModelPicker";

const STATUS_CHIP = {
  pending: "chip-grey",
  running: "chip-amber",
  completed: "chip-green",
  failed: "chip-red",
};

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

// One experiment row: status chip + live progress bar while it runs.
function ExperimentRow({ exp }) {
  const [live, setLive] = useState(exp);

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

  return (
    <Link to={`/experiments/${live.id}`} className="exp-row">
      <div className="exp-row-main">
        <div className="exp-row-name">{live.name}</div>
        <div className="exp-row-meta">
          {live.conditions.length} conditions · created {relTime(live.created_at)}
        </div>
      </div>
      <div className="exp-row-prog">
        {(live.status === "running" || (prog && prog.completed < prog.total)) && (
          <div className="exp-bar" title={`${prog?.completed || 0} / ${prog?.total || 0} cells`}>
            <span style={{ width: `${pct}%` }} />
          </div>
        )}
      </div>
      <span className={`chip ${STATUS_CHIP[live.status] || "chip-grey"}`}>
        {live.status === "running" && <span className="spinner sm" />}
        {live.status}
      </span>
    </Link>
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
  const nameRef = useRef(null);

  const load = useCallback(async () => {
    setLoading(true);
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
          Eight small programs, each with a plain-language requirement, a reference
          implementation, and three deliberately seeded bugs. Seeding is safe to
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
            <ModelPicker />
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

      {/* Experiments list */}
      <section className="section">
        <div className="section-head">
          <h2>Your experiments</h2>
          <span className="count">{loading ? "" : `${experiments.length} total`}</span>
        </div>
        {loading ? (
          <p className="muted" style={{ padding: "8px 0" }}>Loading…</p>
        ) : experiments.length === 0 ? (
          <div className="empty">
            <h3>No experiments yet</h3>
            <p>Seed the benchmark and launch your first study above.</p>
          </div>
        ) : (
          <div className="exp-list">
            {experiments.map((exp) => (
              <ExperimentRow key={exp.id} exp={exp} />
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
