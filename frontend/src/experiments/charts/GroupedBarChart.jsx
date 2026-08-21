import { forwardRef } from "react";

// Grouped bars: one cluster per condition, one bar per metric series, all on a
// shared 0–100 normalised scale so different metrics (fault detection, coverage,
// quality) sit side by side. `series` is [{ key, label, color }]; `groups` is
// [{ key, label, values: { [seriesKey]: 0..100 } }].
const GroupedBarChart = forwardRef(function GroupedBarChart(
  { series = [], groups = [], height = 360, format = (v) => `${Math.round(v)}%` },
  ref
) {
  const W = 720;
  const H = height;
  const m = { t: 30, r: 20, b: 66, l: 52 };
  const iw = W - m.l - m.r;
  const ih = H - m.t - m.b;
  const nG = Math.max(1, groups.length);
  const band = iw / nG;
  const clusterW = band * 0.62;
  const barW = clusterW / Math.max(1, series.length);
  const max = 100;

  const y = (v) => m.t + ih * (1 - Math.max(0, Math.min(1, v / max)));
  const ticks = [0, 25, 50, 75, 100];

  return (
    <svg ref={ref} viewBox={`0 0 ${W} ${H}`} className="ex-chart" role="img" aria-label="Normalised metrics by condition">
      {ticks.map((t, i) => (
        <g key={i}>
          <line x1={m.l} x2={W - m.r} y1={y(t)} y2={y(t)} className="ex-grid" />
          <text x={m.l - 10} y={y(t) + 4} textAnchor="end" className="ex-axis">
            {t}
          </text>
        </g>
      ))}
      <line x1={m.l} x2={W - m.r} y1={y(0)} y2={y(0)} className="ex-axis-line" />

      {groups.map((g, gi) => {
        const cx = m.l + band * gi + band / 2;
        const start = cx - clusterW / 2;
        return (
          <g key={g.key}>
            {series.map((s, si) => {
              const v = g.values[s.key] ?? 0;
              const bx = start + barW * si;
              const top = y(v);
              return (
                <rect
                  key={s.key}
                  x={bx}
                  y={top}
                  width={barW - 3}
                  height={Math.max(0, y(0) - top)}
                  rx="3"
                  fill={s.color}
                >
                  <title>{`${g.label} · ${s.label}: ${format(v)}`}</title>
                </rect>
              );
            })}
            <text x={cx} y={H - m.b + 22} textAnchor="middle" className="ex-xlabel">
              {g.label}
            </text>
          </g>
        );
      })}
    </svg>
  );
});

export default GroupedBarChart;
