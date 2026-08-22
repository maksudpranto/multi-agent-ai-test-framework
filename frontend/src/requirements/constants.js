// Enum option lists mirrored from the backend models (§4-5). Kept in one place
// so the module + requirement forms stay consistent.

export const REQ_TYPES = [
  "user_story",
  "acceptance_criteria",
  "brd",
  "prd",
  "srs",
  "use_case",
  "feature_description",
];

export const REQ_TYPE_LABEL = {
  user_story: "User Story",
  acceptance_criteria: "Acceptance Criteria",
  brd: "BRD",
  prd: "PRD",
  srs: "SRS",
  use_case: "Use Case",
  feature_description: "Feature Description",
};

// The types offered in the New-requirement form. `req_type` is only a label —
// the pipeline reads the requirement text regardless of type — so we surface the
// three that users actually reach for and keep the form uncluttered. (The full
// REQ_TYPES list still drives display labels for any legacy value.)
export const REQ_TYPES_BASIC = [
  "user_story",
  "acceptance_criteria",
  "feature_description",
];

export const PRIORITIES = ["high", "medium", "low"];

export const REQ_STATUSES = ["draft", "ready", "in_progress", "done", "archived"];

export const MODULE_STATUSES = ["active", "on_hold", "completed", "archived"];

export const STATUS_LABEL = {
  on_hold: "On hold",
  in_progress: "In progress",
};

export const label = (map, v) => map[v] || v.replace(/_/g, " ");
