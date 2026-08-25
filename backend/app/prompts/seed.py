"""Seed prompt templates into the database. Prompts are versioned data, not
hardcoded strings, so every AgentExecution can be traced to the exact prompt
that produced it and prompts can be iterated across the thesis.

Idempotent: a (stage, version) pair is inserted once. Bump the version to add
a new revision; the newest active row per stage is used at run time.
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import PipelineStage, PromptTemplate

REQUIREMENT_ANALYSIS_V1 = """\
You are a requirements analyst. Break the following software user story into a \
precise, structured specification for downstream test generation.

USER STORY:
\"\"\"
{user_story}
\"\"\"

Return ONLY a JSON object with exactly these keys:
- "actors": array of strings (the roles/systems involved)
- "preconditions": array of strings (what must be true before the flow)
- "main_flow": array of strings (the primary success path, ordered steps)
- "alt_flows": array of strings (alternative/exception paths)
- "acceptance_criteria": array of objects, each {{"id": "AC1", "text": "..."}} \
with stable sequential ids (AC1, AC2, ...); each criterion must be atomic and \
independently testable
- "ambiguities": array of strings (anything unclear, missing, or contradictory \
in the story that a tester would need clarified)

Do not include any prose outside the JSON.
"""

TEST_GENERATION_V1 = """\
You are a software test designer. Generate precise, independently executable
test cases for this user story and its acceptance criteria.

USER STORY:
{user_story}

ACCEPTANCE CRITERIA (database ids are authoritative):
{acceptance_criteria}

Return ONLY a JSON object with a "test_cases" array. Each item must contain:
- "acceptance_criterion_id": integer id from the supplied criteria
- "title": concise test title
- "steps": non-empty ordered array of imperative steps
- "expected_result": a verifiable outcome
- "type": functional, negative, boundary, or security
- "priority": high, medium, or low

Cover every supplied criterion. Do not include prose outside the JSON.
"""

TEST_GENERATION_V2 = """\
You are a senior test designer. For the user story and its acceptance criteria,
generate a COMPLETE, executable test suite — not one case per criterion, but the
full set a thorough QA engineer would write.

USER STORY:
{user_story}

ACCEPTANCE CRITERIA (database ids are authoritative):
{acceptance_criteria}

For EACH acceptance criterion, produce MULTIPLE test cases spanning the relevant
categories below (skip a category only when it genuinely does not apply):
- functional — the happy path / positive behaviour
- negative   — invalid input, wrong state, denied actions, error handling
- boundary   — edge values: min, max, just-inside, just-outside, empty, zero,
               max length, first/last, off-by-one
- security   — authz/authn, injection, tampering, sensitive-data exposure
- api        — request/response contract, status codes, schema, when the story
               involves an API or service call

Every test case MUST include "test_data": concrete, realistic values needed to
run it — for example {{"valid": {{"email": "a@b.com", "amount": 100}},
"invalid": {{"amount": -1}}, "boundary": [0, 1, 9999999]}}. Use fields that fit
the story's domain. For a pure UI-navigation case with no data, use an empty
object {{}}.

Return ONLY a JSON object with a "test_cases" array. Each item must contain:
- "acceptance_criterion_id": integer id from the supplied criteria
- "title": concise, specific test title
- "steps": non-empty ordered array of imperative, unambiguous steps
- "expected_result": a single verifiable outcome
- "type": functional | negative | boundary | security | api
- "priority": high | medium | low
- "test_data": object or array of concrete data (see above)

Cover every supplied criterion with at least a functional and a negative case.
Do not include prose outside the JSON.
"""

REVIEWER_V1 = """\
You are a meticulous QA reviewer taking part in a multi-agent test-design debate.

DEBATE ROUND: {round}

USER STORY:
{user_story}

ACCEPTANCE CRITERIA (database ids are authoritative):
{acceptance_criteria}

CURRENT TEST CASES (database ids are authoritative):
{test_cases}

Critically review the CURRENT test cases against the story and criteria. Look for:
- missing_scenario  — an acceptance criterion or important path with no test case
- duplicate         — two test cases covering the same behaviour
- weak_steps        — vague/non-executable steps
- wrong_expected    — an expected result that does not verify the behaviour
- untraceable       — a test case not clearly tied to a criterion

Be fair: if the test cases are already adequate, say so instead of inventing issues.

Return ONLY a JSON object:
- "needs_revision": boolean (true if there is at least one finding worth acting on)
- "findings": array of objects, each:
    - "test_case_id": integer id of the offending test case, or null for a missing scenario
    - "acceptance_criterion_id": integer criterion id the issue relates to, or null
    - "issue_type": one of the categories above
    - "severity": "high" | "medium" | "low"
    - "description": what is wrong
    - "suggestion": how to fix it

Do not include prose outside the JSON.
"""

CONSENSUS_V1 = """\
You are the Consensus agent in a multi-agent test-design debate. The reviewer has
raised findings about the current test cases. Respond to EACH finding honestly.

DEBATE ROUND: {round}

USER STORY:
{user_story}

ACCEPTANCE CRITERIA (database ids are authoritative):
{acceptance_criteria}

CURRENT TEST CASES (database ids are authoritative):
{test_cases}

REVIEWER FINDINGS:
{findings}

For each finding decide one of:
- "revise" — you agree; supply an improved "revised_test_case" for that test_case_id
- "keep"   — you disagree; defend the existing test case and explain why the finding
             is rejected (this is a rebuttal — do NOT supply a revised_test_case)
- "add"    — the finding is a real missing scenario; supply a new "revised_test_case"

Return ONLY a JSON object:
- "resolutions": array of objects, each:
    - "test_case_id": integer id of the existing test case, or null when adding
    - "acceptance_criterion_id": integer criterion id, or null
    - "decision": "revise" | "keep" | "add"
    - "rationale": your reasoning (the rebuttal, or why the change is right)
    - "revised_test_case": object with "acceptance_criterion_id" (int), "title",
      "steps" (array), "expected_result", "type", "priority" — required for
      revise/add, omit for keep

Do not include prose outside the JSON.
"""

PRIORITIZATION_V1 = """\
You are a test prioritization specialist. Given the user story and the current
test cases, decide which matter most so a team running under time pressure knows
what to execute first.

USER STORY:
{user_story}

CURRENT TEST CASES (database ids are authoritative):
{test_cases}

For EACH test case, assign:
- "priority": high | medium | low — business importance of the behaviour it checks
- "severity": critical | major | minor — the impact if this behaviour broke in
  production (data loss / security / money = critical)
- "rank": a unique 1-based integer ordering ALL cases from most (1) to least
  important; no ties, no gaps
- "rationale": one short sentence on why

Weigh: security and data-integrity cases high; core happy paths high; obscure
boundary cases lower. Return ONLY a JSON object:
- "rankings": array of objects, each with "test_case_id" (integer, from the
  supplied cases), "priority", "severity", "rank", "rationale"

Do not include prose outside the JSON.
"""

COVERAGE_V1 = """\
You are a test coverage analyst. Each acceptance criterion below is already
mapped (by database id) to the test cases that trace to it. Traceability is
authoritative — do NOT re-decide which case maps where. Your job is to judge, per
criterion, whether that mapping is ADEQUATE or only superficial.

USER STORY:
{user_story}

ACCEPTANCE CRITERIA WITH THEIR MAPPED TEST CASES:
{coverage_map}

For EACH criterion decide:
- "adequate": true if the mapped cases genuinely and sufficiently verify the
  criterion (positive AND relevant negative/boundary behaviour where it matters);
  false if there are no cases, or they only skim the surface (e.g. happy path
  only, missing error handling, missing edge values)
- "gap_notes": a short sentence naming what is missing, or "Adequately covered"

Return ONLY a JSON object:
- "assessments": array of objects, each with "acceptance_criterion_id" (integer),
  "adequate" (boolean), "gap_notes" (string)

Do not include prose outside the JSON.
"""

QUALITY_V1 = """\
You are a test quality evaluator. Score the quality of each test case so a team
knows which cases are well-formed and which need rework. This is the thesis's
Quality Report.

USER STORY:
{user_story}

CURRENT TEST CASES (database ids are authoritative):
{test_cases}

Score EACH test case on a 0.0–1.0 scale (1.0 = excellent):
- "clarity": are the steps and expected result unambiguous and executable?
- "atomicity": does it verify ONE thing (not a bundle of unrelated checks)?
- "traceability": is it clearly tied to a specific requirement / acceptance
  criterion?
- "duplicate": true if this case substantially overlaps another in the set
- "notes": one short sentence on the main quality issue, or "Well-formed"

Return ONLY a JSON object:
- "scores": array of objects, each with "test_case_id" (integer), "clarity"
  (number), "atomicity" (number), "traceability" (number), "duplicate"
  (boolean), "notes" (string)

Do not include prose outside the JSON.
"""

SINGLE_LLM_BASELINE_V1 = """\
You are a software tester. This is a SINGLE-LLM BASELINE: in one step, read the
user story and write test cases for it. There is no separate analysis phase.

USER STORY:
{user_story}

Return ONLY a JSON object with a "test_cases" array. Each item must contain:
- "title": concise test title
- "steps": non-empty ordered array of imperative steps
- "expected_result": a verifiable outcome
- "type": functional, negative, boundary, or security
- "priority": high, medium, or low

Do not include prose outside the JSON.
"""

TEST_DATA_V1 = """\
You are a test-data engineer. Produce concrete, realistic sample data that makes
the following ONE test case executable — actual values a tester could paste in
and run, not descriptions.

USER STORY (domain context):
{user_story}

TEST CASE:
{test_case}

Return ONLY a JSON object with a single key "test_data" whose value fits the
case's type and domain:
- For a data-driven case, use {{"valid": {{...}}, "invalid": {{...}},
  "boundary": [...]}} — realistic field names and values drawn from the story,
  invalid values that should be rejected, and boundary/edge values (min, max,
  just-inside, just-outside, empty, zero, max length, off-by-one).
- For a boundary-type case, emphasise the edge values that matter.
- For a negative/security case, emphasise the invalid or malicious inputs.
- For a pure UI-navigation case with no real data, return {{"test_data": {{}}}}.

Use the same units and field names the story implies. Do not restate the steps
or include any prose outside the JSON.
"""

SEED_PROMPTS: list[dict] = [
    {
        "stage": PipelineStage.requirement_analysis,
        "version": "v1",
        "template": REQUIREMENT_ANALYSIS_V1,
        "description": "Requirement analysis: user story -> structured spec.",
    },
    {
        "stage": PipelineStage.test_generation,
        "version": "v1",
        "template": TEST_GENERATION_V1,
        "description": "Test generation: acceptance criteria -> traceable test cases.",
    },
    {
        # v2 is the active generator: a full suite per criterion (functional,
        # negative, boundary, security, api) with concrete test_data. Seeded
        # after v1 so get_active_prompt (newest active per stage) selects it.
        "stage": PipelineStage.test_generation,
        "version": "v2",
        "template": TEST_GENERATION_V2,
        "description": "Rich generation: full test suite per criterion + mock data + edge cases.",
    },
    {
        "stage": PipelineStage.test_data,
        "version": "v1",
        "template": TEST_DATA_V1,
        "description": "Test data: concrete sample data for one test case, on demand.",
    },
    {
        "stage": PipelineStage.reviewer,
        "version": "v1",
        "template": REVIEWER_V1,
        "description": "Reviewer: critique current test cases, emit needs_revision verdict.",
    },
    {
        "stage": PipelineStage.consensus,
        "version": "v1",
        "template": CONSENSUS_V1,
        "description": "Consensus: rebut/revise/add per reviewer finding.",
    },
    {
        "stage": PipelineStage.prioritization,
        "version": "v1",
        "template": PRIORITIZATION_V1,
        "description": "Prioritizer: assign priority/severity/rank to each test case.",
    },
    {
        "stage": PipelineStage.coverage,
        "version": "v1",
        "template": COVERAGE_V1,
        "description": "Coverage: judge adequacy of each criterion's traced cases.",
    },
    {
        "stage": PipelineStage.quality,
        "version": "v1",
        "template": QUALITY_V1,
        "description": "Quality: score each test case (clarity/atomicity/traceability) + duplicates.",
    },
    {
        # Single-LLM baseline. Kept inactive so it never shadows the multi-agent
        # test_generation prompt in get_active_prompt; the baseline path fetches
        # it explicitly by version via get_prompt().
        "stage": PipelineStage.test_generation,
        "version": "baseline_v1",
        "template": SINGLE_LLM_BASELINE_V1,
        "description": "Single-LLM baseline: user story -> test cases in one prompt.",
        "is_active": False,
    },
]


def seed_prompts(db: Session) -> int:
    """Insert any missing (stage, version) prompt rows. Returns count inserted."""
    inserted = 0
    for row in SEED_PROMPTS:
        exists = db.scalar(
            select(PromptTemplate).where(
                PromptTemplate.stage == row["stage"],
                PromptTemplate.version == row["version"],
            )
        )
        if exists:
            continue
        data = {**row}
        is_active = data.pop("is_active", True)
        db.add(PromptTemplate(**data, is_active=is_active))
        inserted += 1
    if inserted:
        db.commit()
    return inserted


def get_prompt(db: Session, stage: PipelineStage, version: str) -> PromptTemplate | None:
    """Fetch a specific prompt by (stage, version) — used for prompts that are
    intentionally inactive, like the single-LLM baseline."""
    return db.scalar(
        select(PromptTemplate).where(
            PromptTemplate.stage == stage,
            PromptTemplate.version == version,
        )
    )


def get_active_prompt(db: Session, stage: PipelineStage) -> PromptTemplate | None:
    """Newest active template for a stage."""
    return db.scalar(
        select(PromptTemplate)
        .where(PromptTemplate.stage == stage, PromptTemplate.is_active.is_(True))
        .order_by(PromptTemplate.created_at.desc(), PromptTemplate.id.desc())
    )
