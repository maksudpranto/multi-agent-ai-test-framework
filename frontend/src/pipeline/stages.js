// The end-to-end product flow. "Add User Story" is the last implemented step in
// Phase 0; every stage after it is a placeholder the later build phases fill in.
export const PIPELINE_STAGES = [
  { key: "add_user_story", label: "Add User Story", implemented: true },
  { key: "requirement_analysis", label: "Requirement Analysis", implemented: false },
  { key: "generate_test_cases", label: "Generate Test Cases", implemented: false },
  { key: "reviewer_agent", label: "Reviewer Agent", implemented: false },
  { key: "consensus_agent", label: "Consensus Agent", implemented: false },
  { key: "coverage_analysis", label: "Coverage Analysis", implemented: false },
  { key: "quality_evaluation", label: "Quality Evaluation", implemented: false },
  { key: "manual_review", label: "Manual Review", implemented: false },
  { key: "export", label: "Export", implemented: false },
];
