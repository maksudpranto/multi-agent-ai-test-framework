import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "../api/client";
import BarChart from "./charts/BarChart";
import GroupedBarChart from "./charts/GroupedBarChart";
import { conditionColor, METRIC_COLOR } from "./charts/palette";
import { downloadCsv, svgToPng } from "./charts/chartExport";

// --- metric display metadata ------------------------------------------------
const pct01 = (v) => `${Math.round((v ?? 0) * 100)}%`;
const num2 = (v) => (v ?? 0).toFixed(2);
const int0 = (v) => Math.round(v ?? 0).toLocaleString();
const ms = (v) => `${Math.round((v ?? 0) / 100) / 10}s`;

const METRICS = [
  { key: "mutation_score", label: "Fault detection", fmt: pct01, better: "high",
    tip: "Mutation score — the share of seeded bugs the generated suite actually caught. The headline result." },
  { key: "coverage_pct", label: "Coverage", fmt: (v) => `${Math.round(v ?? 0)}%`, better: "high",
    tip: "Percent of acceptance criteria with at least one tracing test case." },
  { key: "quality_score", label: "Quality", fmt: num2, better: "high",
    tip: "Mean of clarity, atomicity and traceability (0–1), judged by the Quality agent." },
  { key: "n_test_cases", label: "Test cases", fmt: (v) => int0(v), better: "high",
    tip: "Average number of test cases in the suite." },
  { key: "duplicate_rate", label: "Duplicates", fmt: pct01, better: "low",
    tip: "Fraction of near-duplicate cases — lower is better." },
  { key: "rounds_to_consensus", label: "Debate rounds", fmt: num2, better: "none",
    tip: "Reviewer⇄Consensus rounds used before agreement." },
  { key: "tokens_total", label: "Tokens", fmt: int0, better: "none",
    tip: "Total tokens spent per run (cost)." },
  { key: "latency_ms_total", label: "Latency", fmt: ms, better: "none",
    tip: "Total wall-clock time per run." },
];

function Info({ tip }) {
  return (
    <span className="ex-info" tabIndex={0} title={tip} aria-label={tip}>
      i
    </span>
  );
}

// Winner (best mean) per metric column, honoring direction; null when neutral.
function winnerKey(conditions, metric) {
  if (metric.better === "none") return null;
  let best = null;
  for (const c of conditions) {
    const s = c.metrics[metric.key];
    if (!s || s.n === 0) continue;
    if (
      best === null ||
      (metric.better === "high" && s.mean > best.mean) ||
      (metric.better === "low" && s.mean < best.mean)
    ) {
      best = { key: c.key, mean: s.mean };
    }
  }
  return best?.key ?? null;
}

export default function ExperimentResults() {
  const { experimentId } = useParams();
  const [results, setResults] = useState(null);
  const [error, setError] = useState("");
  const [items, setItems] = useState([]);
  const barRef = useRef(null);
  const groupRef = useRef(null);

  const fetchResults = useCallback(async () => {
    try {
      const data = await api.getExperimentResults(experimentId);
      setResults(data);
      return data;
    } catch (err) {
      setError(err.message);
      return null;
    }
  }, [experimentId]);

  useEffect(() => {
    fetchResults();
  }, [fetchResults]);

  // Poll while the study is still running.
  useEffect(() => {
    const status = results?.progress?.status;
    if (status !== "running" && status !== "pending") return undefined;
    const id = setInterval(fetchResults, 3000);
    return () => clearInterval(id);
  }, [results?.progress?.status, fetchResults]);

  // Benchmark items for the drill-down (once we know the dataset).
  const datasetId = results?.experiment?.dataset_id;
  useEffect(() => {
    if (!datasetId) return;
    api.listBenchmarkItems(datasetId).then(setItems).catch(() => {});
  }, [datasetId]);

  const conditions = results?.conditions ?? [];
  const orderedConditions = useMemo(
    () => [...conditions].sort((a, b) => (b.is_baseline ? -1 : 0) - (a.is_baseline ? -1 : 0)),
    [conditions]
  );

  if (error) return <div className="content"><p className="error">{error}</p></div>;
  if (!results) return <div className="content"><p className="muted">Loading…</p></div>;

  const exp = results.experiment;
  const prog = results.progress;
  const running = prog.status === "running" || prog.status === "pending";
  const headline = results.headline;

  // --- figures data ---
  const faultData = orderedConditions
    .filter((c) => c.metrics.mutation_score)
    .map((c) => ({
      key: c.key,
      label: c.label,
      value: c.metrics.mutation_score.mean,
      color: conditionColor(c.key),
    }));

  const seriesDefs = [
    { key: "mutation_score", label: "Fault detection", scale: 100 },
    { key: "coverage_pct", label: "Coverage", scale: 1 },
    { key: "quality_score", label: "Quality", scale: 100 },
  ].filter((s) => orderedConditions.some((c) => c.metrics[s.key]));
  const series = seriesDefs.map((s) => ({ key: s.key, label: s.label, color: METRIC_COLOR[s.key] }));
  const groups = orderedConditions.map((c) => ({
    key: c.key,
    label: c.label,
    values: Object.fromEntries(
      seriesDefs.map((s) => [s.key, (c.metrics[s.key]?.mean ?? 0) * s.scale])
    ),
  }));

  // --- exports ---
  function exportCsv() {
    const header = ["Condition", "n valid", ...METRICS.map((m) => `${m.label} (mean)`), ...METRICS.map((m) => `${m.label} (std)`)];
    const rows = [header];
    for (const c of orderedConditions) {
      rows.push([
        c.label,
        c.n_valid,
        ...METRICS.map((m) => (c.metrics[m.key] ? c.metrics[m.key].mean : "")),
        ...METRICS.map((m) => (c.metrics[m.key] ? c.metrics[m.key].std : "")),
      ]);
    }
    rows.push([]);
    rows.push(["Comparison vs baseline", "n pairs", "baseline mean", "condition mean", "delta", "% improvement", "p-value (Wilcoxon)", "Cohen's dz", "wins", "losses", "ties", "significant"]);
    for (const cmp of results.comparisons) {
      if (cmp.insufficient_data) continue;
      rows.push([
        cmp.condition_label || cmp.condition,
        cmp.n_pairs, cmp.baseline_mean, cmp.condition_mean, cmp.mean_delta,
        cmp.pct_improvement, cmp.p_value, cmp.cohens_dz, cmp.wins, cmp.losses, cmp.ties,
        cmp.significant ? "yes" : "no",
      ]);
    }
    downloadCsv(`experiment-${exp.id}-results`, rows);
  }

  return (
    <div className="content exp-results">
      <div className="exp-res-top">
        <div>
          <Link to="/experiments" className="back-link">← Experiments</Link>
          <h1>{exp.name}</h1>
          <p className="muted">
            {results.n_items} programs · {orderedConditions.length} conditions ·{" "}
            <span className={`chip ${running ? "chip-amber" : prog.status === "failed" ? "chip-red" : "chip-green"}`}>
              {running && <span className="spinner sm" />}
              {prog.status}
            </span>
          </p>
        </div>
        <div className="exp-res-actions">
          <button className="ghost" onClick={exportCsv}>Export CSV</button>
          <button className="ghost" onClick={() => svgToPng(barRef.current, `experiment-${exp.id}-fault-detection`)}>
            Export chart (PNG)
          </button>
        </div>
      </div>

      {running && (
        <div className="exp-progress-banner">
          <div className="exp-bar big"><span style={{ width: `${prog.pct}%` }} /></div>
          <span>{prog.completed} / {prog.total} cells complete{prog.failed ? ` · ${prog.failed} failed` : ""}</span>
        </div>
      )}

      {/* Headline */}
      {headline?.available && (
        <HeadlineCallout headline={headline} conditions={orderedConditions} />
      )}

      {/* Fault-detection tiles */}
      <section className="section">
        <div className="section-head">
          <h2>Fault detection by condition <Info tip="How many of the seeded bugs each condition's suites caught, averaged over the benchmark. This is the thesis's core measure." /></h2>
        </div>
        <div className="fd-tiles">
          {orderedConditions.map((c) => {
            const s = c.metrics.mutation_score;
            const isWinner = headline?.winner === c.key;
            return (
              <div key={c.key} className={`fd-tile ${isWinner ? "win" : ""} ${c.is_baseline ? "base" : ""}`}>
                {isWinner && <span className="fd-crown">Best</span>}
                <div className="fd-name" style={{ "--dot": conditionColor(c.key) }}>
                  <span className="fd-dot" /> {c.label}
                </div>
                <div className="fd-score">{s ? pct01(s.mean) : "—"}</div>
                <div className="fd-sub">
                  {c.is_baseline ? "baseline" : "of seeded faults caught"}
                  {s && s.n > 0 ? ` · n=${s.n}` : ""}
                </div>
              </div>
            );
          })}
        </div>
        <figure className="ex-figure">
          <BarChart ref={barRef} data={faultData} max={1} format={pct01} />
          <figcaption>Mean mutation score per condition (higher = more bugs caught).</figcaption>
        </figure>
      </section>

      {/* Significance */}
      {results.comparisons?.length > 0 && (
        <section className="section">
          <div className="section-head">
            <h2>Statistical significance <Info tip="Each condition is compared to the single-LLM baseline with a Wilcoxon signed-rank test, paired by program. p < 0.05 means the difference is unlikely to be chance." /></h2>
          </div>
          <div className="sig-grid">
            {results.comparisons.map((cmp) => (
              <SignificanceCard key={cmp.condition} cmp={cmp} />
            ))}
          </div>
        </section>
      )}

      {/* Normalised metric comparison */}
      {series.length > 1 && (
        <section className="section">
          <div className="section-head">
            <h2>All metrics, normalised <Info tip="Fault detection, coverage and quality on a shared 0–100 scale so conditions can be compared at a glance." /></h2>
          </div>
          <figure className="ex-figure">
            <div className="ex-legend">
              {series.map((s) => (
                <span key={s.key} className="ex-leg"><i style={{ background: s.color }} />{s.label}</span>
              ))}
            </div>
            <GroupedBarChart ref={groupRef} series={series} groups={groups} />
          </figure>
        </section>
      )}

      {/* Summary table */}
      <section className="section">
        <div className="section-head">
          <h2>Summary <Info tip="Mean ± standard deviation for every metric. The best value in each column is highlighted." /></h2>
        </div>
        <div className="table-wrap">
          <table className="ex-table">
            <thead>
              <tr>
                <th>Condition</th>
                {METRICS.map((m) => (
                  <th key={m.key}>{m.label} <Info tip={m.tip} /></th>
                ))}
              </tr>
            </thead>
            <tbody>
              {orderedConditions.map((c) => (
                <tr key={c.key}>
                  <td className="ex-td-name">
                    <span className="fd-dot" style={{ "--dot": conditionColor(c.key), background: conditionColor(c.key) }} />
                    {c.label}
                  </td>
                  {METRICS.map((m) => {
                    const s = c.metrics[m.key];
                    const isWin = winnerKey(orderedConditions, m) === c.key;
                    return (
                      <td key={m.key} className={isWin ? "ex-win" : ""}>
                        {s ? (
                          <>
                            {m.fmt(s.mean)}
                            {s.n > 1 && <span className="ex-std"> ±{m.fmt(s.std)}</span>}
                          </>
                        ) : "—"}
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      {/* Per-item drill-down */}
      {items.length > 0 && (
        <section className="section">
          <div className="section-head">
            <h2>Per-program breakdown <Info tip="Open a program to see the suite each condition produced and exactly which bugs it caught." /></h2>
          </div>
          <div className="drill-list">
            {items.map((it) => (
              <DrilldownItem key={it.id} item={it} experimentId={exp.id} />
            ))}
          </div>
        </section>
      )}
    </div>
  );
}

function HeadlineCallout({ headline, conditions }) {
  const cmp = headline.comparison;
  const winnerIsBaseline = conditions.find((c) => c.key === headline.winner)?.is_baseline;
  const scorePct = `${Math.round(headline.winner_mutation_score * 100)}%`;

  let body;
  if (winnerIsBaseline || !cmp) {
    body = (
      <>The <b>{headline.winner_label}</b> scored highest at <b>{scorePct}</b> fault detection —
        no condition beat the baseline by a significant margin here.</>
    );
  } else {
    const delta = cmp.pct_improvement != null ? `+${cmp.pct_improvement}%` : `+${Math.round(cmp.mean_delta * 100)} pts`;
    body = (
      <>The <b>{headline.winner_label}</b> caught <b>{scorePct}</b> of seeded faults — <b>{delta}</b> over
        the single-LLM baseline{cmp.significant
          ? <>, and the difference is <b>statistically significant</b> (p={cmp.p_value}, Wilcoxon).</>
          : <>, though the difference is <b>not statistically significant</b> (p={cmp.p_value}).</>}</>
    );
  }

  return (
    <div className={`headline-callout ${cmp?.significant ? "sig" : ""}`}>
      <div className="hc-icon" aria-hidden>
        <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <path d="M20 6 9 17l-5-5" />
        </svg>
      </div>
      <p>{body}</p>
    </div>
  );
}

function SignificanceCard({ cmp }) {
  if (cmp.insufficient_data) {
    return (
      <div className="sig-card">
        <div className="sig-name">{cmp.condition_label || cmp.condition}</div>
        <p className="muted">Not enough valid pairs to test.</p>
      </div>
    );
  }
  const delta = cmp.pct_improvement != null ? `${cmp.pct_improvement > 0 ? "+" : ""}${cmp.pct_improvement}%` : "—";
  return (
    <div className={`sig-card ${cmp.significant ? "sig" : ""}`}>
      <div className="sig-head">
        <div className="sig-name">{cmp.condition_label || cmp.condition} <span className="sig-vs">vs baseline</span></div>
        <span className={`chip ${cmp.significant ? "chip-green" : "chip-grey"}`}>
          {cmp.significant ? "significant" : "n.s."}
        </span>
      </div>
      <div className="sig-delta">{delta}<span className="sig-delta-cap">fault detection</span></div>
      <div className="sig-stats">
        <div><b>p={cmp.p_value}</b><span>Wilcoxon</span></div>
        <div><b>{cmp.cohens_dz ?? "—"}</b><span>Cohen's dz</span></div>
        <div><b>{cmp.wins}/{cmp.losses}/{cmp.ties}</b><span>win/lose/tie</span></div>
      </div>
    </div>
  );
}

function DrilldownItem({ item, experimentId }) {
  const [open, setOpen] = useState(false);
  const [detail, setDetail] = useState(null);
  const [loading, setLoading] = useState(false);

  async function toggle() {
    const next = !open;
    setOpen(next);
    if (next && !detail) {
      setLoading(true);
      try {
        setDetail(await api.getExperimentItem(experimentId, item.requirement_id));
      } catch {
        /* ignore */
      } finally {
        setLoading(false);
      }
    }
  }

  return (
    <div className={`drill ${open ? "open" : ""}`}>
      <button className="drill-head" onClick={toggle} aria-expanded={open}>
        <span className="drill-caret">▸</span>
        <span className="drill-title">{item.title}</span>
        <code className="drill-fn">{item.entrypoint}()</code>
        <span className="drill-mut">{item.n_mutants} bugs</span>
      </button>
      {open && (
        <div className="drill-body">
          {loading && <p className="muted">Loading…</p>}
          {detail && (
            <div className="drill-conds">
              {detail.conditions.map((c) => {
                const mut = c.metrics?.mutation_score;
                const killed = c.metrics?.mutants_killed;
                const total = c.metrics?.mutants_total;
                return (
                  <div key={c.condition} className="drill-cond">
                    <div className="drill-cond-head">
                      <span className="fd-dot" style={{ "--dot": conditionColor(c.condition), background: conditionColor(c.condition) }} />
                      <b>{c.label}</b>
                      <span className="drill-cond-score">
                        {mut != null ? `${Math.round(mut * 100)}% caught` : "—"}
                        {killed != null && total != null ? ` (${killed}/${total})` : ""}
                      </span>
                    </div>
                    <div className="drill-cases">
                      {(c.test_cases || []).length} test case{(c.test_cases || []).length === 1 ? "" : "s"}
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
