// Colours for the experiment figures, drawn from the app's design tokens so the
// charts read as part of the same system (see index.css). The baseline is a
// deliberate neutral grey; the full pipeline gets the indigo accent so the eye
// lands on the framework being evaluated.

export const CONDITION_COLOR = {
  single_llm: "#9498a2", // baseline — neutral grey
  full_pipeline: "#4f46e5", // accent indigo — the full framework
  ablation_no_debate: "#7c3aed", // mauve
  ablation_no_reviewer: "#0ea5e9",
  orchestrator: "#16a34a",
};

const FALLBACK = ["#4f46e5", "#0ea5e9", "#16a34a", "#d97706", "#db2777", "#7c3aed"];

export function conditionColor(key, i = 0) {
  return CONDITION_COLOR[key] || FALLBACK[i % FALLBACK.length];
}

// Metric series colours for the normalised grouped chart.
export const METRIC_COLOR = {
  mutation_score: "#4f46e5",
  coverage_pct: "#0ea5e9",
  quality_score: "#16a34a",
};
