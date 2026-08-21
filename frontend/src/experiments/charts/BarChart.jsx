import { forwardRef } from "react";

// A single-metric vertical bar chart (one bar per condition), hand-rolled in SVG
// to match the app's aesthetic and export cleanly to PNG. `data` is
// [{ key, label, value, color }]; `format` renders the value label on each bar.
const BarChart = forwardRef(function BarChart(
  { data = [], max = 1, format = (v) => v, height = 340, yTicks = 4 },
  ref
) {
  const W = 720;
  const H = height;
  const m = { t: 30, r: 20, b: 66, l: 52 };
  const iw = W - m.l - m.r;
  const ih = H - m.t - m.b;
  const n = Math.max(1, data.length);
  const band = iw / n;
  const barW = Math.min(110, band * 0.5);

  const y = (v) => m.t + ih * (1 - Math.max(0, Math.min(1, v / max)));
  const ticks = Array.from({ length: yTicks + 1 }, (_, i) => (max * i) / yTicks);

  return (
    <svg ref={ref} viewBox={`0 0 ${W} ${H}`} className="ex-chart" role="img" aria-label="Fault detection by condition">
      {/* y grid + labels */}
      {ticks.map((t, i) => (
        <g key={i}>
          <line x1={m.l} x2={W - m.r} y1={y(t)} y2={y(t)} className="ex-grid" />
          <text x={m.l - 10} y={y(t) + 4} textAnchor="end" className="ex-axis">
            {format(t)}
          </text>
        </g>
      ))}
      {/* baseline */}
      <line x1={m.l} x2={W - m.r} y1={y(0)} y2={y(0)} className="ex-axis-line" />

      {/* bars */}
      {data.map((d, i) => {
        const cx = m.l + band * i + band / 2;
        const top = y(d.value);
        const h = y(0) - top;
        return (
          <g key={d.key}>
            <rect
              x={cx - barW / 2}
              y={top}
              width={barW}
              height={Math.max(0, h)}
              rx="5"
              fill={d.color}
            >
              <title>{`${d.label}: ${format(d.value)}`}</title>
            </rect>
            <text x={cx} y={top - 9} textAnchor="middle" className="ex-barval">
              {format(d.value)}
            </text>
            <text x={cx} y={H - m.b + 22} textAnchor="middle" className="ex-xlabel">
              {d.label}
            </text>
          </g>
        );
      })}
    </svg>
  );
});

export default BarChart;
