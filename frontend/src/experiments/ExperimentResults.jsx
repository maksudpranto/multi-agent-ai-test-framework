import { Fragment, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { api } from "../api/client";
import GroupedBarChart from "./charts/GroupedBarChart";
import { conditionColor, METRIC_COLOR } from "./charts/palette";
import { downloadCsv } from "./charts/chartExport";

// --- metric display metadata ------------------------------------------------
const pct01 = (v) => `${Math.round((v ?? 0) * 100)}%`;
const num2 = (v) => (v ?? 0).toFixed(2);
const int0 = (v) => Math.round(v ?? 0).toLocaleString();
const ms = (v) => `${Math.round((v ?? 0) / 100) / 10}s`;

const METRICS = [
  { key: "mutation_score", label: "Bugs caught", fmt: pct01, better: "high",
    tip: "The share of the planted bugs this approach's tests actually caught — the headline result." },
  { key: "coverage_pct", label: "Rules covered", fmt: (v) => `${Math.round(v ?? 0)}%`, better: "high",
    tip: "The share of the requirement's rules that have at least one test." },
  { key: "quality_score", label: "Test quality", fmt: num2, better: "high",
    tip: "How clear, focused and well-linked the tests are (0–1), judged by the Quality agent." },
  { key: "n_test_cases", label: "Tests written", fmt: (v) => int0(v), better: "high",
    tip: "How many test cases the suite contains." },
  { key: "duplicate_rate", label: "Duplicate tests", fmt: pct01, better: "low",
    tip: "The share of tests that are near-duplicates of another — lower is better." },
  { key: "rounds_to_consensus", label: "Self-review rounds", fmt: num2, better: "none",
    tip: "How many rounds of critique-and-fix the agents ran before agreeing. Only the agent team does this." },
  { key: "tokens_total", label: "Tokens used", fmt: int0, better: "none",
    tip: "How much work the AI did, measured in tokens — the main cost." },
  { key: "faults_per_1k_tokens", label: "Bugs per 1k tokens", fmt: num2, better: "high",
    tip: "Bugs caught for every 1,000 tokens spent — the 'is it worth the cost?' number." },
  { key: "latency_ms_total", label: "Time per run", fmt: ms, better: "none",
    tip: "How long one run took." },
];

// Grouped for the metric table so related numbers sit together.
const METRIC_GROUPS = [
  { title: "How good are the tests?", keys: ["mutation_score", "coverage_pct", "quality_score", "duplicate_rate", "n_test_cases"] },
  { title: "What did it cost?", keys: ["rounds_to_consensus", "tokens_total", "faults_per_1k_tokens", "latency_ms_total"] },
];
const METRIC_BY_KEY = Object.fromEntries(METRICS.map((m) => [m.key, m]));

// Plain-language names for the fault taxonomy (mirrors the backend corpus).
const FAULT_LABELS = {
  boundary: "Boundary",
  wrong_constant: "Wrong value",
  wrong_operator: "Wrong operator",
  missing_condition: "Missing check",
  control_flow: "Control flow",
};

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

// The agent team's pipeline — shown so the reader sees this is agent-based, not
// one monolithic prompt. Each stage is a specialised agent with one job.
const AGENT_STAGES = [
  { name: "Analyst", note: "reads the requirement" },
  { name: "Generator", note: "writes the tests" },
  { name: "Reviewer ⇄ Consensus", note: "debate & fix", debate: true },
  { name: "Coverage", note: "checks every rule is tested" },
  { name: "Quality", note: "flags weak / duplicate tests" },
];

// Classify a condition as the single-AI baseline or an agent team (full or
// ablated), so the page can label the two contenders in plain language.
function conditionKind(c) {
  if (c.is_baseline) return { team: false, tag: "Single AI", sub: "one AI, one prompt" };
  if (/ablation|no[_-]?debate/i.test(c.key)) return { team: true, tag: "Agent team", sub: "no self-review" };
  return { team: true, tag: "Agent team", sub: "reviews its own tests" };
}

function TeamIcon() {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.9" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
      <circle cx="7" cy="8" r="2.4" /><circle cx="17" cy="8" r="2.4" />
      <path d="M3.5 18a3.5 3.5 0 0 1 7 0M13.5 18a3.5 3.5 0 0 1 7 0" />
    </svg>
  );
}
function SingleIcon() {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.9" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
      <circle cx="12" cy="8" r="3" /><path d="M5.5 19a6.5 6.5 0 0 1 13 0" />
    </svg>
  );
}

// The agent-team assembly line — a numbered, connected list so it reads as a
// clear sequence of hand-offs no matter how narrow the card gets.
function AgentPipeline() {
  return (
    <ol className="xr-pipe" aria-label="Agent pipeline">
      {AGENT_STAGES.map((s, i) => (
        <li key={s.name} className={`xr-pipe-step ${s.debate ? "debate" : ""}`}>
          <span className="xr-pipe-num">{i + 1}</span>
          <span className="xr-pipe-txt"><b>{s.name}</b><em>{s.note}</em></span>
        </li>
      ))}
    </ol>
  );
}

// The five steps of the experiment method. Showing this flow is what makes the
// page's purpose click — the reader sees it's a controlled experiment, not a chart.
const FLOW_STEPS = [
  { title: "A requirement", note: "a plain-English feature to test" },
  { title: "Two approaches write tests", note: "a single AI vs a 5-agent team" },
  { title: "We plant bugs", note: "seed real faults into the code" },
  { title: "Count the catches", note: "run each suite, see which bugs die" },
  { title: "Compare", note: "score it, then test for significance" },
];

function HowItWorks() {
  return (
    <div className="xr-how">
      <span className="xr-how-title">How this experiment works</span>
      <ol className="xr-flow">
        {FLOW_STEPS.map((s, i) => (
          <li className="xr-flow-item" key={s.title}>
            <div className="xr-flow-step">
              <span className="xr-flow-num">{i + 1}</span>
              <span className="xr-flow-b">{s.title}</span>
              <span className="xr-flow-s">{s.note}</span>
            </div>
            {i < FLOW_STEPS.length - 1 && <span className="xr-flow-arrow" aria-hidden>→</span>}
          </li>
        ))}
      </ol>
    </div>
  );
}

function cap(s) { return s ? s.charAt(0).toUpperCase() + s.slice(1) : s; }

// One recitable paragraph — literally the script for explaining the whole page.
function AtAGlance({ results, headline, conditions }) {
  if (!headline?.available) return null;
  const cmp = headline.comparison;
  const winner = conditions.find((c) => c.key === headline.winner);
  const who = winner?.is_baseline ? "the single AI" : "the agent team";
  const scorePct = `${Math.round(headline.winner_mutation_score * 100)}%`;
  const reps = results.n_reps > 1 ? `, averaged over ${results.n_reps} repeated runs` : "";

  let outcome;
  if (winner?.is_baseline || !cmp) {
    outcome = <>{cap(who)} came out on top, catching <b>{scorePct}</b> — no approach won by a meaningful margin.</>;
  } else {
    const delta = cmp.pct_improvement != null ? `${cmp.pct_improvement}%` : `${Math.round(cmp.mean_delta * 100)} points`;
    outcome = (
      <>{cap(who)} caught the most — <b>{scorePct}</b>, <b>{delta} more</b> than a single AI{cmp.significant
        ? <>, a <b>statistically significant</b> gap (p={cmp.p_value}).</>
        : <>, though <b>not yet a statistically significant</b> gap (p={cmp.p_value}).</>}</>
    );
  }
  return (
    <div className="xr-glance">
      <span className="xr-glance-label">In one line</span>
      <p>
        This experiment pitted <b>{conditions.length} approaches</b> against <b>{results.n_items} programs</b>{reps}.
        Each program hides <b>4 planted bugs</b>, and we counted how many each approach's tests catch. {outcome}
      </p>
    </div>
  );
}

// Orientation: what this page is, the recitable summary, and how it works.
function ExperimentBrief({ results, headline, conditions }) {
  return (
    <section className="xr-brief">
      <span className="xr-eyebrow">Experiment · fault-based evidence</span>
      <h2 className="xr-q">Do a <em>team</em> of AI agents write better tests than a <em>single</em> AI?</h2>
      <p className="xr-lead">
        This page is the evidence. It runs the same requirements through a single AI and an
        agent team, plants real bugs in the code, and measures whose tests catch more.
      </p>
      <AtAGlance results={results} headline={headline} conditions={conditions} />
      <HowItWorks />
      <details className="xr-meet">
        <summary><span className="xr-det-caret" aria-hidden>▸</span> Meet the agent team — five specialists that hand off in a pipeline</summary>
        <AgentPipeline />
      </details>
    </section>
  );
}

// A section heading carrying its step number in the page's argument.
function StepHead({ n, title, tip, aside }) {
  return (
    <div className="section-head">
      <h2><span className="xr-step">{n}</span>{title} {tip && <Info tip={tip} />}</h2>
      {aside}
    </div>
  );
}

// The merged result: one row per approach — identity, a bar, and its score — so
// the cards and the chart become a single, clean leaderboard (no duplication).
function ResultLeaderboard({ rows }) {
  return (
    <div className="xr-result">
      <div className="xr-result-rows">
        {rows.map((d) => (
          <div key={d.key} className={`xr-rrow ${d.best ? "best" : ""} ${d.team ? "team" : "single"}`} style={{ "--dot": d.color }}>
            <div className="xr-rid">
              <div className="xr-rtop">
                {d.team ? <TeamIcon /> : <SingleIcon />}
                <span className="xr-rname">{d.label}</span>
                {d.best && <span className="xr-rbest">Best</span>}
              </div>
              <div className="xr-rsub">{d.sub}</div>
            </div>
            <div className="xr-rtrack">
              <div className="xr-rfill" style={{ width: `${Math.max(2, Math.round(d.value * 100))}%`, background: d.color }} />
            </div>
            <div className="xr-rval">
              {pct01(d.value)}
              {d.spread != null && <span className="xr-rspread">± {pct01(d.spread)}</span>}
            </div>
          </div>
        ))}
      </div>
      <div className="xr-rscale" aria-hidden>
        <span />
        <div className="xr-rscale-ticks">
          {[0, 25, 50, 75, 100].map((t) => <span key={t}>{t}%</span>)}
        </div>
        <span />
      </div>
    </div>
  );
}

// Plain-language cost trade-off: the agent team is more thorough but spends more.
function CostCallout({ conditions, step }) {
  const team = conditions.find((c) => !c.is_baseline && /full/i.test(c.key)) || conditions.find((c) => !c.is_baseline);
  const single = conditions.find((c) => c.is_baseline);
  const tok = (c) => c?.metrics?.tokens_total?.mean;
  const eff = (c) => c?.metrics?.faults_per_1k_tokens?.mean;
  if (!team || !single || tok(team) == null || tok(single) == null) return null;
  const ratio = tok(single) ? tok(team) / tok(single) : null;
  const ratioText = ratio ? (ratio >= 10 ? `~${Math.round(ratio)}×` : `${ratio.toFixed(1)}×`) : "—";
  const effTeam = eff(team);
  const effSingle = eff(single);
  return (
    <section className="section">
      <StepHead n={step} title="What did the extra agents cost?" tip="The agent team runs several agents and a self-review round, so it does much more work — measured in 'tokens', the AI's unit of work — than a single prompt." />
      <div className="xr-cost">
        <div className="xr-cost-cell">
          <div className="xr-cost-big">{ratioText}</div>
          <div className="xr-cost-cap">more work than a single AI<br /><span className="muted">{int0(tok(team))} vs {int0(tok(single))} tokens per run</span></div>
        </div>
        {effTeam != null ? (
          <div className="xr-cost-cell">
            <div className="xr-cost-big">{effTeam.toFixed(1)}</div>
            <div className="xr-cost-cap">bugs caught for every 1,000 tokens<br /><span className="muted">single AI: {effSingle != null ? effSingle.toFixed(1) : "—"}</span></div>
          </div>
        ) : (
          <div className="xr-cost-cell">
            <div className="xr-cost-cap">The agent team caught more bugs, but spent far more doing it. Whether that trade is worth it depends on how much catching each extra bug matters to you.</div>
          </div>
        )}
      </div>
      <p className="muted xr-cost-take">
        In plain terms: the agent team is more thorough, but roughly {ratioText.replace("~", "")} the cost of a single AI.
      </p>
    </section>
  );
}

export default function ExperimentResults() {
  const { experimentId } = useParams();
  const navigate = useNavigate();
  const [results, setResults] = useState(null);
  const [error, setError] = useState("");
  const [items, setItems] = useState([]);
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

  // --- step numbers: count only the sections that will actually render, so the
  // argument always reads 1..N with no gaps (some sections hide on legacy runs). ---
  const ftHasData = !!(
    results.fault_types?.by_condition &&
    Object.values(results.fault_types.by_condition).some((rows) => rows && Object.keys(rows).length)
  );
  const costBase = orderedConditions.find((c) => c.is_baseline);
  const costTeam = orderedConditions.find((c) => !c.is_baseline && /full/i.test(c.key))
    || orderedConditions.find((c) => !c.is_baseline);
  const hasCost = !!(costTeam && costBase
    && costTeam.metrics?.tokens_total?.mean != null && costBase.metrics?.tokens_total?.mean != null);
  const hasSig = results.comparisons?.length > 0;
  // A quick run covers only a subset of programs — list exactly those that ran.
  const ranIds = new Set(results.ran_requirement_ids || []);
  const shownItems = ranIds.size ? items.filter((it) => ranIds.has(it.requirement_id)) : items;
  const hasEvidence = shownItems.length > 0;
  let stepK = 1;
  const stepResult = stepK++;
  const stepFaults = ftHasData ? stepK++ : null;
  const stepSig = hasSig ? stepK++ : null;
  const stepCost = hasCost ? stepK++ : null;
  const stepEvidence = hasEvidence ? stepK++ : null;

  // --- merged result rows: identity + score, sorted best-first ---
  const resultRows = orderedConditions
    .filter((c) => c.metrics.mutation_score)
    .map((c) => {
      const kind = conditionKind(c);
      const s = c.metrics.mutation_score;
      // Row name is the short tag ("Agent team" / "Single AI") so every row is a
      // single line of equal height; the distinguishing descriptor and the sample
      // size go on the sub line.
      return {
        key: c.key,
        label: kind.tag,
        value: s.mean,
        color: conditionColor(c.key),
        team: kind.team,
        sub: s.n > 0 ? `${kind.sub} · across ${s.n} program${s.n === 1 ? "" : "s"}` : kind.sub,
        best: headline?.winner === c.key,
        spread: c.n_reps > 1 && c.run_to_run_std != null ? c.run_to_run_std : null,
      };
    })
    .sort((a, b) => b.value - a.value);

  const seriesDefs = [
    { key: "mutation_score", label: "Bugs caught", scale: 100 },
    { key: "coverage_pct", label: "Rules covered", scale: 1 },
    { key: "quality_score", label: "Test quality", scale: 100 },
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
    // Fault detection by bug type (killed/total and rate per condition).
    const ft = results.fault_types;
    if (ft?.legend?.length) {
      rows.push([]);
      rows.push(["Fault detection by bug type", ...orderedConditions.flatMap((c) => [`${c.label} caught`, `${c.label} seeded`, `${c.label} rate`])]);
      for (const f of ft.legend) {
        const cells = orderedConditions.flatMap((c) => {
          const r = ft.by_condition?.[c.key]?.[f.key];
          return r && r.total > 0 ? [r.killed, r.total, r.rate] : ["", "", ""];
        });
        if (cells.some((v) => v !== "")) rows.push([f.label, ...cells]);
      }
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
            {results.n_items} programs · {orderedConditions.length} approaches ·{" "}
            <span className={`chip ${running ? "chip-amber" : prog.status === "failed" ? "chip-red" : "chip-green"}`}>
              {running && <span className="spinner sm" />}
              {prog.status}
            </span>
          </p>
        </div>
        <div className="exp-res-actions">
          {running && (
            <button className="ghost" onClick={async () => {
              try { await api.stopExperiment(exp.id); fetchResults(); } catch (e) { alert(e.message); }
            }}>Stop</button>
          )}
          <button className="ghost" onClick={async () => {
            const name = prompt("Rename experiment:", exp.name);
            if (name && name.trim()) {
              try { await api.renameExperiment(exp.id, name.trim()); fetchResults(); } catch (e) { alert(e.message); }
            }
          }}>Rename</button>
          <button className="ghost" onClick={exportCsv}>Export CSV</button>
          <button className="ghost danger" disabled={running} title={running ? "Stop it first" : "Delete experiment"}
            onClick={async () => {
              if (confirm(`Delete "${exp.name}"? This removes the experiment and all its runs and results.`)) {
                try { await api.deleteExperiment(exp.id); navigate("/experiments"); } catch (e) { alert(e.message); }
              }
            }}>Delete</button>
        </div>
      </div>

      {running && (
        <div className="exp-progress-banner">
          <div className="exp-bar big"><span style={{ width: `${prog.pct}%` }} /></div>
          <span>{prog.completed} / {prog.total} cells complete{prog.failed ? ` · ${prog.failed} failed` : ""}</span>
        </div>
      )}

      {/* Orientation: what this page is, a recitable summary, and how it works */}
      <ExperimentBrief results={results} headline={headline} conditions={orderedConditions} />

      {/* 1 — The result */}
      <section className="section">
        <StepHead
          n={stepResult}
          title="The result: who caught more bugs?"
          tip="The share of seeded bugs each approach's suites caught, averaged over every program. This is the thesis's core measure."
          aside={results.n_reps > 1 ? <span className="muted">averaged over {results.n_reps} runs · ± = run-to-run spread</span> : null}
        />
        <ResultLeaderboard rows={resultRows} />
      </section>

      {/* 2 — Which kinds of bug */}
      {ftHasData && (
        <FaultTypeBreakdown faultTypes={results.fault_types} conditions={orderedConditions} step={stepFaults} />
      )}

      {/* 3 — Is the difference real */}
      {hasSig && (
        <section className="section">
          <StepHead n={stepSig} title="Is the difference real, or luck?" tip="Each agent condition is compared to the single-AI baseline with a Wilcoxon signed-rank test, paired by program. p < 0.05 means the gap is unlikely to be chance." />
          <div className="sig-grid">
            {results.comparisons.map((cmp) => (
              <SignificanceCard key={cmp.condition} cmp={cmp} />
            ))}
          </div>
        </section>
      )}

      {/* 4 — What did the extra agents cost */}
      <CostCallout conditions={orderedConditions} step={stepCost} />

      {/* All the numbers — folded away by default to keep the page clean */}
      <details className="xr-details">
        <summary>
          <span className="xr-det-caret" aria-hidden>▸</span>
          <span className="xr-det-title">All the numbers</span>
          <span className="muted">full metric table &amp; normalised chart</span>
        </summary>
        <div className="xr-details-body">
          {series.length > 1 && (
            <figure className="ex-figure">
              <div className="ex-legend">
                {series.map((s) => (
                  <span key={s.key} className="ex-leg"><i style={{ background: s.color }} />{s.label}</span>
                ))}
              </div>
              <GroupedBarChart ref={groupRef} series={series} groups={groups} />
            </figure>
          )}
          <div className="table-wrap">
            <table className="ex-table xr-mt">
              <thead>
                <tr>
                  <th className="xr-mt-col-name">Metric</th>
                  {orderedConditions.map((c) => (
                    <th key={c.key}>
                      <span className="fd-dot" style={{ "--dot": conditionColor(c.key), background: conditionColor(c.key) }} />
                      {c.label}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {METRIC_GROUPS.map((g) => {
                  const keys = g.keys.filter(
                    (k) => METRIC_BY_KEY[k] && orderedConditions.some((c) => c.metrics[k] != null)
                  );
                  if (keys.length === 0) return null;
                  return (
                    <Fragment key={g.title}>
                      <tr className="xr-mt-group">
                        <td colSpan={orderedConditions.length + 1}>{g.title}</td>
                      </tr>
                      {keys.map((key) => {
                        const m = METRIC_BY_KEY[key];
                        const winner = winnerKey(orderedConditions, m);
                        return (
                          <tr key={key}>
                            <td className="xr-mt-name">{m.label} <Info tip={m.tip} /></td>
                            {orderedConditions.map((c) => {
                              const s = c.metrics[m.key];
                              const isWin = winner === c.key;
                              return (
                                <td key={c.key} className={isWin ? "ex-win" : ""}>
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
                        );
                      })}
                    </Fragment>
                  );
                })}
              </tbody>
            </table>
          </div>
          <p className="muted xr-mt-note">
            “—” means not measured for that approach — e.g. a single AI has no rules-covered, quality, or self-review step.
          </p>
        </div>
      </details>

      {/* 5 — The evidence, program by program */}
      {hasEvidence && (
        <section className="section">
          <StepHead n={stepEvidence} title="The evidence, program by program" tip="Open a program to see the suite each approach produced and exactly which bugs it caught." />
          <div className="drill-list">
            {shownItems.map((it) => (
              <DrilldownItem key={it.id} item={it} experimentId={exp.id} />
            ))}
          </div>
        </section>
      )}
    </div>
  );
}

function SignificanceCard({ cmp }) {
  const name = cmp.condition_label || cmp.condition;
  if (cmp.insufficient_data) {
    return (
      <div className="sig-card">
        <div className="sig-name">{name} <span className="sig-vs">vs Single AI</span></div>
        <p className="muted">Not enough data to judge yet.</p>
      </div>
    );
  }
  const better = (cmp.mean_delta ?? 0) >= 0;
  const delta = cmp.pct_improvement != null
    ? `${cmp.pct_improvement > 0 ? "+" : ""}${cmp.pct_improvement}%`
    : "—";
  const n = cmp.n_pairs;
  const verdict = cmp.significant ? "Likely real" : "Could be luck";
  const plain = cmp.significant
    ? "The gap is big and consistent enough that it's probably real — unlikely to be down to chance."
    : "The gap is small enough that it could just be chance. Running more programs would show whether it holds up.";
  return (
    <div className={`sig-card ${cmp.significant ? "sig" : ""}`}>
      <div className="sig-head">
        <div className="sig-name">{name} <span className="sig-vs">vs Single AI</span></div>
        <span className={`sig-verdict ${cmp.significant ? "good" : "weak"}`}>{verdict}</span>
      </div>
      <div className="sig-delta">{delta}<span className="sig-delta-cap">{better ? "more bugs caught" : "fewer bugs caught"}</span></div>
      <p className="sig-plain">{plain}</p>
      <div className="sig-evidence">
        <span className="sig-ev-main">
          Ahead on <b>{cmp.wins}</b> of {n} program{n === 1 ? "" : "s"}
          {cmp.ties ? `, tied on ${cmp.ties}` : ""}
          {cmp.losses ? `, behind on ${cmp.losses}` : ""}
        </span>
        <span className="sig-ev-maths">
          the maths <Info tip={`p-value = ${cmp.p_value} (how likely this gap is pure chance — below 0.05 means unlikely). Effect size (Cohen's dz) = ${cmp.cohens_dz ?? "—"} (how big the gap is relative to its variability). Test: Wilcoxon signed-rank, paired by program.`} />
        </span>
      </div>
    </div>
  );
}

// Fault detection broken down by the KIND of bug (boundary, wrong value, …).
// The sharper thesis result: not just "multi-agent catches more" but *which*
// classes of bug it closes the gap on versus the baseline.
function FaultTypeBreakdown({ faultTypes, conditions, step }) {
  const legend = faultTypes?.legend || [];
  const byCond = faultTypes?.by_condition || {};

  // Which fault classes actually have data in any condition.
  const rows = legend
    .map((f) => {
      const cells = conditions.map((c) => {
        const r = byCond[c.key]?.[f.key];
        return { key: c.key, label: c.label, ...(r || {}) };
      });
      const anyData = cells.some((x) => x.total > 0);
      return { ...f, cells, anyData };
    })
    .filter((r) => r.anyData);

  if (rows.length === 0) return null;

  // Best condition per row (highest detection rate) to highlight the gap.
  const bestForRow = (cells) => {
    let best = null;
    for (const x of cells) {
      if (x.rate == null) continue;
      if (best === null || x.rate > best.rate) best = x;
    }
    return best?.key ?? null;
  };

  return (
    <section className="section">
      <StepHead n={step} title="Which kinds of bug did each catch?" tip="Every seeded bug is labelled with the kind of mistake it represents. This shows which classes of bug each approach catches — e.g. whether the agent team closes the boundary/edge-case gap a single AI leaves open." />
      <div className="table-wrap">
        <table className="ex-table ft-table">
          <thead>
            <tr>
              <th>Bug type</th>
              {conditions.map((c) => (
                <th key={c.key}>
                  <span className="fd-dot" style={{ "--dot": conditionColor(c.key), background: conditionColor(c.key) }} />
                  {c.label}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => {
              const winKey = bestForRow(r.cells);
              return (
                <tr key={r.key}>
                  <td className="ex-td-name">
                    {r.label} <Info tip={r.blurb} />
                  </td>
                  {r.cells.map((x) => (
                    <td key={x.key} className={winKey === x.key && r.cells.length > 1 ? "ex-win" : ""}>
                      {x.total > 0 ? (
                        <>
                          {pct01(x.rate)}
                          <span className="ex-std"> {x.killed}/{x.total}</span>
                        </>
                      ) : "—"}
                    </td>
                  ))}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <p className="muted ft-note">Share of each bug type caught, pooled across every program and run. The count is bugs caught / bugs of that type seeded.</p>
    </section>
  );
}

function fmtInput(args) {
  if (!Array.isArray(args)) return String(args);
  return args.map((a) => JSON.stringify(a)).join(", ");
}

// A one-word column label for the bug matrix header.
function shortApproach(c) {
  if (c.is_baseline) return "Single AI";
  if (/ablation|no[_-]?debate/i.test(c.condition)) return "No self-review";
  return "Agent team";
}

// One planted bug: fault-type badge + plain description, a caught/missed mark per
// approach, and — when opened — the buggy code and the exact input that caught it.
function BugRow({ mutant, conditions, cols }) {
  const [open, setOpen] = useState(false);
  const perCond = conditions.map((c) => {
    const pm = (c.detail?.per_mutant || []).find((m) => m.key === mutant.key);
    return { c, killed: pm ? pm.killed : null, by: pm?.killed_by_input };
  });
  return (
    <div className={`xrb ${open ? "open" : ""}`}>
      <button className="xrb-head" style={{ gridTemplateColumns: cols }} onClick={() => setOpen((o) => !o)} aria-expanded={open}>
        <span className="xrb-desc">
          <span className="xrb-caret" aria-hidden>▸</span>
          {mutant.fault_type && (
            <span className={`ft-badge ft-${mutant.fault_type}`}>{FAULT_LABELS[mutant.fault_type] || mutant.fault_type}</span>
          )}
          <span className="xrb-text">{mutant.description}</span>
        </span>
        {perCond.map(({ c, killed }) => (
          <span
            key={c.condition}
            className={`xrb-v ${killed === null ? "na" : killed ? "ok" : "miss"}`}
            style={killed ? { "--dot": conditionColor(c.condition) } : undefined}
            title={`${c.label}: ${killed === null ? "not scored" : killed ? "caught" : "missed"}`}
          >
            {killed === null ? "—" : killed ? "✓" : "✗"}
          </span>
        ))}
      </button>
      {open && (
        <div className="xrb-body">
          <div className="xrb-code">
            <span className="xrb-code-label">The bug that was planted</span>
            <pre>{mutant.code}</pre>
          </div>
          <div className="xrb-catches">
            {perCond.map(({ c, killed, by }) => (
              <div key={c.condition} className={`xrb-catch ${killed ? "ok" : killed === null ? "na" : "miss"}`}>
                <span className="xrb-catch-name">
                  <span className="fd-dot" style={{ background: conditionColor(c.condition) }} />
                  {c.label}
                </span>
                <span className="xrb-catch-verdict">
                  {killed === null ? "not scored" : killed
                    ? <>caught with <code>{fmtInput(by)}</code></>
                    : "missed this bug"}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function DrilldownItem({ item, experimentId }) {
  const [open, setOpen] = useState(false);
  const [detail, setDetail] = useState(null);
  const [loading, setLoading] = useState(false);
  const [showCases, setShowCases] = useState(null); // condition key whose cases are shown

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

  // Single AI (baseline) first as the control, then the agent teams.
  const conditions = [...(detail?.conditions || [])].sort(
    (a, b) => (b.is_baseline ? 1 : 0) - (a.is_baseline ? 1 : 0)
  );
  const mutants = detail?.item?.mutants || [];
  const cols = `1fr ${"96px ".repeat(conditions.length).trim()}`;

  // Highlight a "best" approach only when there's a real difference between them.
  const rates = conditions
    .map((c) => (c.metrics?.mutants_total ? c.metrics.mutants_killed / c.metrics.mutants_total : null))
    .filter((x) => x != null);
  const maxRate = rates.length ? Math.max(...rates) : null;
  const hasWinner = rates.length > 1 && maxRate > Math.min(...rates);

  const requirement = (detail?.item?.requirement_text || "")
    .split(/\n\s*\n/)[0]?.replace(/\s*\n\s*/g, " ").trim();

  return (
    <div className={`xrd ${open ? "open" : ""}`}>
      <button className="xrd-head" onClick={toggle} aria-expanded={open}>
        <span className="xrd-caret" aria-hidden>▸</span>
        <span className="xrd-title">{item.title}</span>
        <code className="xrd-fn">{item.entrypoint}()</code>
        <span className="xrd-nbugs">{item.n_mutants} seeded bugs</span>
      </button>
      {open && (
        <div className="xrd-body">
          {loading && <p className="muted xrd-loading">Loading…</p>}
          {detail && (
            <>
              {requirement && (
                <div className="xrd-req">
                  <span className="xrd-req-label">Requirement under test</span>
                  <p>{requirement}</p>
                </div>
              )}

              {/* Scoreboard: how each approach did on this program */}
              <div className="xrd-board">
                {conditions.map((c) => {
                  const kind = conditionKind({ is_baseline: c.is_baseline, key: c.condition });
                  const killed = c.metrics?.mutants_killed;
                  const total = c.metrics?.mutants_total;
                  const nCases = (c.test_cases || []).length;
                  const isBest = hasWinner && total && killed / total === maxRate;
                  return (
                    <div
                      key={c.condition}
                      className={`xrd-score ${kind.team ? "team" : "single"} ${isBest ? "best" : ""}`}
                      style={{ "--dot": conditionColor(c.condition) }}
                    >
                      <div className="xrd-score-top">
                        <span className="xrd-score-kind">{kind.team ? <TeamIcon /> : <SingleIcon />}{c.label}</span>
                        {isBest && <span className="xrd-score-best">Best</span>}
                      </div>
                      <div className="xrd-score-frac">
                        {killed != null && total != null
                          ? <><b>{killed}</b><span className="xrd-frac-den">/{total}</span><em>bugs caught</em></>
                          : <span className="muted">not scored</span>}
                      </div>
                      {total != null && (
                        <div className="xrd-dots" aria-hidden>
                          {Array.from({ length: total }).map((_, i) => (
                            <span key={i} className={`xrd-dot ${i < killed ? "on" : ""}`} />
                          ))}
                        </div>
                      )}
                      <button
                        className={`xrd-viewcases ${showCases === c.condition ? "active" : ""}`}
                        onClick={() => setShowCases(showCases === c.condition ? null : c.condition)}
                      >
                        {showCases === c.condition ? "Hide" : "View"} {nCases} test{nCases === 1 ? "" : "s"}
                      </button>
                    </div>
                  );
                })}
              </div>

              {/* The chosen approach's test cases */}
              {showCases && (() => {
                const cc = conditions.find((c) => c.condition === showCases);
                const cases = cc?.test_cases || [];
                return (
                  <div className="xrd-cases-panel">
                    <div className="xrd-cases-head">
                      <span className="fd-dot" style={{ background: conditionColor(showCases) }} />
                      {cases.length} test{cases.length === 1 ? "" : "s"} written by {cc?.label}
                    </div>
                    {cases.length > 0 ? (
                      <ol className="xrd-cases">
                        {cases.map((tc) => (
                          <li key={tc.id}>
                            <b>{tc.title}</b>
                            {tc.type && <span className="tc-type">{tc.type}</span>}
                          </li>
                        ))}
                      </ol>
                    ) : <p className="muted">No test cases in this suite.</p>}
                  </div>
                );
              })()}

              {/* Bug-by-bug matrix */}
              {mutants.length > 0 ? (
                <div className="xrd-bugs-block">
                  <div className="xrd-bugs-title">
                    Which bugs did each approach catch?
                    <span className="muted">✓ caught · ✗ missed · click a bug to see its code</span>
                  </div>
                  <div className="xrd-matrix">
                    <div className="xrd-mhead" style={{ gridTemplateColumns: cols }}>
                      <span>Planted bug</span>
                      {conditions.map((c) => (
                        <span key={c.condition} className="xrd-mcol" title={c.label}>
                          <span className="fd-dot" style={{ background: conditionColor(c.condition) }} />
                          {shortApproach(c)}
                        </span>
                      ))}
                    </div>
                    {mutants.map((m) => (
                      <BugRow key={m.key} mutant={m} conditions={conditions} cols={cols} />
                    ))}
                  </div>
                </div>
              ) : (
                <p className="muted">Per-bug detail isn't available for this run.</p>
              )}
            </>
          )}
        </div>
      )}
    </div>
  );
}
