// End-to-end product flow. UI uses human labels (no "Agent" — that term lives
// in the architecture docs only). `implemented` flips on as each build phase
// lands.
export const PIPELINE_STAGES = [
  { key: "add_user_story", label: "Add User Story", implemented: true },
  { key: "requirement_analysis", label: "Requirement Analysis", implemented: true },
  { key: "test_generation", label: "Test Generation", implemented: true },
  { key: "review", label: "Review", implemented: true },
  { key: "consensus", label: "Consensus", implemented: true },
  { key: "coverage", label: "Coverage", implemented: false },
  { key: "quality", label: "Quality Evaluation", implemented: false },
  { key: "manual_review", label: "Manual Review", implemented: false },
  { key: "export", label: "Export", implemented: false },
];
