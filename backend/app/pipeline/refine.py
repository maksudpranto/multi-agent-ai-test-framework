"""Human-in-the-loop refinement.

Takes a user's plain-language suggestion and the current test suite, and asks the
model to either apply it (when it's a valid, in-scope change) or reject it with a
short reason. Deliberately conservative: the model must justify every edit, and we
only ever touch cases it explicitly names. Edits are versioned like any other
change to the suite (revise -> new version, remove -> rejected, add -> new case),
so coverage/quality/export stay consistent.
"""
from __future__ import annotations

import json

from sqlalchemy.orm import Session

from app.llm.service import LLMService
from app.models import (
    AcceptanceCriterion,
    GeneratedBy,
    PipelineRun,
    TestCase,
    TestCaseStatus,
)

REFINE_SYSTEM = (
    "You are a meticulous QA lead refining an existing test suite from a single "
    "user suggestion. Apply the suggestion ONLY if it is a sensible, in-scope "
    "change to the test suite for the given requirement. REJECT it (applied=false) "
    "if it is out of scope, contradicts the requirement, is unsafe, or is "
    "nonsensical. Never invent behaviour the requirement does not state. Change as "
    "little as possible. Respond with STRICT JSON only — no prose outside the JSON."
)

_PRIORITIES = {"high", "medium", "low"}


def _cases_payload(cases: list[TestCase]) -> list[dict]:
    return [
        {
            "id": c.id,
            "title": c.title,
            "type": c.type,
            "priority": c.priority,
            "steps": c.steps or [],
            "expected_result": c.expected_result,
            "traces_to": c.traces_to,
        }
        for c in cases
    ]


def _build_prompt(
    requirement_text: str,
    criteria: list[AcceptanceCriterion],
    cases: list[TestCase],
    suggestion: str,
) -> str:
    crit_lines = "\n".join(f"{c.id}: {c.text}" for c in criteria) or "(none)"
    return (
        f"REQUIREMENT:\n{requirement_text}\n\n"
        f"ACCEPTANCE CRITERIA (id: text):\n{crit_lines}\n\n"
        f"CURRENT TEST SUITE (JSON):\n{json.dumps(_cases_payload(cases), indent=2)}\n\n"
        f"USER SUGGESTION:\n{suggestion}\n\n"
        "Decide whether the suggestion is a valid change to THIS suite, then respond "
        "with JSON of exactly this shape:\n"
        "{\n"
        '  "applied": true or false,\n'
        '  "reason": "one short sentence addressed to the user",\n'
        '  "operations": [\n'
        '    {"op": "add", "title": "...", "type": "functional|negative|boundary|edge|security", '
        '"priority": "high|medium|low", "steps": ["..."], "expected_result": "...", '
        '"traces_to": <criterion id or null>},\n'
        '    {"op": "revise", "id": <existing case id>, "title": "...", "type": "...", '
        '"priority": "...", "steps": ["..."], "expected_result": "...", "traces_to": <criterion id or null>},\n'
        '    {"op": "remove", "id": <existing case id>}\n'
        "  ]\n"
        "}\n"
        "Rules: if applied is false, operations MUST be an empty list. For a revise, "
        "include the full updated fields and keep the id referencing the CURRENT "
        "suite. Only reference case ids and criterion ids that appear above."
    )


def refine_suite(
    *,
    db: Session,
    run: PipelineRun,
    requirement_text: str,
    criteria: list[AcceptanceCriterion],
    cases: list[TestCase],
    suggestion: str,
    service: LLMService,
    model: str,
) -> dict:
    """Returns {applied: bool, reason: str, changed: int}. Persists on apply."""
    prompt = _build_prompt(requirement_text, criteria, cases, suggestion)
    try:
        parsed, _ = service.complete_json(
            prompt=prompt, model=model, system=REFINE_SYSTEM, temperature=0.0
        )
    except Exception as exc:  # no JSON / provider error — surface, don't crash
        return {
            "applied": False,
            "reason": f"Couldn't process that suggestion ({exc}). Try rephrasing it.",
        }

    if not isinstance(parsed, dict):
        return {
            "applied": False,
            "reason": "The model returned an unexpected response. Try rephrasing.",
        }

    applied = bool(parsed.get("applied"))
    reason = str(parsed.get("reason") or ("Applied." if applied else "Not applied."))
    if not applied:
        return {"applied": False, "reason": reason}

    by_id = {c.id: c for c in cases}
    valid_ac = {c.id for c in criteria}

    def clean_trace(v):
        return v if v in valid_ac else None

    def clean_priority(v, fallback="medium"):
        v = (v or "").lower().strip()
        return v if v in _PRIORITIES else fallback

    changed = 0
    for op in parsed.get("operations") or []:
        kind = (op.get("op") or "").lower().strip()
        if kind == "remove":
            tc = by_id.get(op.get("id"))
            if tc:
                tc.status = TestCaseStatus.rejected
                changed += 1
        elif kind == "revise":
            old = by_id.get(op.get("id"))
            if not old:
                continue
            db.add(
                TestCase(
                    pipeline_run_id=run.id,
                    parent_test_case_id=old.id,
                    title=op.get("title", old.title),
                    type=op.get("type", old.type),
                    priority=clean_priority(op.get("priority"), old.priority or "medium"),
                    steps=op.get("steps", old.steps),
                    expected_result=op.get("expected_result", old.expected_result),
                    test_data=old.test_data,
                    traces_to=clean_trace(op.get("traces_to")) or old.traces_to,
                    severity=old.severity,
                    rank=old.rank,
                    generated_by=GeneratedBy.manual,
                    status=TestCaseStatus.manual_approved,
                    version=(old.version or 1) + 1,
                )
            )
            changed += 1
        elif kind == "add":
            title = (op.get("title") or "").strip()
            if not title:
                continue
            db.add(
                TestCase(
                    pipeline_run_id=run.id,
                    title=title,
                    type=op.get("type"),
                    priority=clean_priority(op.get("priority")),
                    steps=op.get("steps") or [],
                    expected_result=op.get("expected_result"),
                    traces_to=clean_trace(op.get("traces_to")),
                    generated_by=GeneratedBy.manual,
                    status=TestCaseStatus.manual_approved,
                    version=1,
                )
            )
            changed += 1

    if changed == 0:
        return {
            "applied": False,
            "reason": reason or "No concrete change could be applied from that suggestion.",
        }

    db.commit()
    return {"applied": True, "reason": reason, "changed": changed}
