// Colours for the experiment figures — a monochrome ramp so the charts read as
// part of the black-and-white theme (see index.css). Conditions are separated by
// shade rather than hue: the baseline is the lightest grey, the full pipeline is
// near-black so the eye lands on the framework being evaluated.

export const CONDITION_COLOR = {
  single_llm: "#a6a9b0", // baseline — light grey
  full_pipeline: "#18181b", // near-black — the full framework
  ablation_no_debate: "#55565c", // mid grey
  ablation_no_reviewer: "#7c7e86", // grey
  orchestrator: "#34343a", // dark grey
};

const FALLBACK = ["#18181b", "#55565c", "#7c7e86", "#a6a9b0", "#2a2a30", "#c3c5cb"];

export function conditionColor(key, i = 0) {
  return CONDITION_COLOR[key] || FALLBACK[i % FALLBACK.length];
}

// Metric series colours for the normalised grouped chart — three greyscale steps.
export const METRIC_COLOR = {
  mutation_score: "#18181b",
  coverage_pct: "#6c707a",
  quality_score: "#adb0b7",
};
