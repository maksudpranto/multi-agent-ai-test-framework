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
