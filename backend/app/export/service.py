"""Assemble and serialize the Complete Test Design Package (§10).

One place builds a normalized package dict from a pipeline run's artifacts (the
five primary evaluated outputs: test cases, test data, requirement traceability,
coverage, quality). Serializers render it to JSON / CSV / Markdown / Excel / PDF
so the same content is exported consistently across formats.
"""
from __future__ import annotations

import csv
import io
import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    AcceptanceCriterion,
    CoverageReport,
    PipelineRun,
    QualityReport,
    Requirement,
    TestCase,
    TestCaseStatus,
)

FORMATS = {
    "json": ("application/json", "json"),
    "csv": ("text/csv", "csv"),
    "md": ("text/markdown", "md"),
    "xlsx": (
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "xlsx",
    ),
    "pdf": ("application/pdf", "pdf"),
}


def _current_test_cases(db: Session, run: PipelineRun) -> list[TestCase]:
    all_cases = list(
        db.scalars(
            select(TestCase)
            .where(TestCase.pipeline_run_id == run.id)
            .order_by(TestCase.id)
        )
    )
    superseded = {c.parent_test_case_id for c in all_cases if c.parent_test_case_id}
    current = [
        c
        for c in all_cases
        if c.id not in superseded and c.status != TestCaseStatus.rejected
    ]
    current.sort(key=lambda c: (c.rank if c.rank is not None else 10_000, c.id))
    return current


def build_package(db: Session, run: PipelineRun, requirement: Requirement) -> dict:
    """Normalized package for one run — the shape every serializer consumes."""
    criteria = list(
        db.scalars(
            select(AcceptanceCriterion)
            .where(AcceptanceCriterion.pipeline_run_id == run.id)
            .order_by(AcceptanceCriterion.order)
        )
    )
    cases = _current_test_cases(db, run)
    coverage = list(
        db.scalars(
            select(CoverageReport).where(CoverageReport.pipeline_run_id == run.id)
        )
    )
    quality = {
        q.test_case_id: q
        for q in db.scalars(
            select(QualityReport).where(QualityReport.pipeline_run_id == run.id)
        )
    }
    crit_label = {c.id: f"AC{i + 1}" for i, c in enumerate(criteria)}

    return {
        "requirement": {
            "id": requirement.id,
            "title": requirement.title,
            "type": requirement.req_type.value
            if hasattr(requirement.req_type, "value")
            else requirement.req_type,
            "priority": requirement.priority.value
            if hasattr(requirement.priority, "value")
            else requirement.priority,
            "text": requirement.raw_text,
        },
        "acceptance_criteria": [
            {"id": c.id, "label": crit_label[c.id], "text": c.text} for c in criteria
        ],
        "test_cases": [
            {
                "id": c.id,
                "title": c.title,
                "type": c.type,
                "priority": c.priority,
                "severity": c.severity,
                "rank": c.rank,
                "traces_to": crit_label.get(c.traces_to),
                "steps": c.steps or [],
                "expected_result": c.expected_result,
                "test_data": c.test_data,
                "quality": (
                    {
                        "clarity": quality[c.id].clarity_score,
                        "atomicity": quality[c.id].atomicity_score,
                        "traceability": quality[c.id].traceability_score,
                        "duplicate": quality[c.id].duplicate_flag,
                    }
                    if c.id in quality
                    else None
                ),
            }
            for c in cases
        ],
        "coverage": [
            {
                "criterion": crit_label.get(r.acceptance_criterion_id),
                "covered": r.covered,
                "covering_test_case_ids": r.covering_test_case_ids or [],
                "gap_notes": r.gap_notes,
            }
            for r in coverage
        ],
    }


# --- serializers ----------------------------------------------------------


def _steps_text(steps: list) -> str:
    return " | ".join(f"{i + 1}. {s}" for i, s in enumerate(steps))


def to_json(pkg: dict) -> bytes:
    return json.dumps(pkg, indent=2, ensure_ascii=False).encode("utf-8")


def to_csv(pkg: dict) -> bytes:
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(
        [
            "id", "title", "type", "priority", "severity", "rank",
            "traces_to", "steps", "expected_result", "test_data",
            "clarity", "atomicity", "traceability", "duplicate",
        ]
    )
    for tc in pkg["test_cases"]:
        q = tc.get("quality") or {}
        w.writerow(
            [
                tc["id"], tc["title"], tc["type"], tc["priority"],
                tc.get("severity") or "", tc.get("rank") if tc.get("rank") is not None else "",
                tc.get("traces_to") or "", _steps_text(tc["steps"]),
                tc["expected_result"] or "",
                json.dumps(tc.get("test_data")) if tc.get("test_data") else "",
                q.get("clarity", ""), q.get("atomicity", ""),
                q.get("traceability", ""), q.get("duplicate", ""),
            ]
        )
    return buf.getvalue().encode("utf-8")


def to_markdown(pkg: dict) -> bytes:
    r = pkg["requirement"]
    lines = [
        f"# Test Design Package — {r['title']}",
        "",
        f"**Type:** {r['type']} · **Priority:** {r['priority']}",
        "",
        "## Requirement",
        "",
        r["text"],
        "",
        "## Acceptance Criteria",
        "",
    ]
    for c in pkg["acceptance_criteria"]:
        lines.append(f"- **{c['label']}** — {c['text']}")
    lines += ["", "## Test Cases", ""]
    for tc in pkg["test_cases"]:
        lines.append(
            f"### {tc['title']}  \n"
            f"`{tc['type']}` · priority {tc['priority']}"
            + (f" · severity {tc['severity']}" if tc.get("severity") else "")
            + (f" · {tc['traces_to']}" if tc.get("traces_to") else "")
        )
        for i, s in enumerate(tc["steps"]):
            lines.append(f"{i + 1}. {s}")
        lines.append(f"- **Expected:** {tc['expected_result']}")
        if tc.get("test_data"):
            lines.append(f"- **Test data:** `{json.dumps(tc['test_data'])}`")
        q = tc.get("quality")
        if q:
            lines.append(
                f"- **Quality:** clarity {q['clarity']}, atomicity {q['atomicity']}, "
                f"traceability {q['traceability']}"
                + (" · duplicate" if q.get("duplicate") else "")
            )
        lines.append("")
    lines += ["## Coverage", ""]
    for c in pkg["coverage"]:
        mark = "✓" if c["covered"] else "✗ gap"
        lines.append(f"- **{c['criterion']}**: {mark} — {c['gap_notes'] or ''}")
    return ("\n".join(lines) + "\n").encode("utf-8")


def to_xlsx(pkg: dict) -> bytes:
    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active
    ws.title = "Test Cases"
    ws.append(
        ["ID", "Title", "Type", "Priority", "Severity", "Rank", "Traces To",
         "Steps", "Expected Result", "Test Data",
         "Clarity", "Atomicity", "Traceability", "Duplicate"]
    )
    for tc in pkg["test_cases"]:
        q = tc.get("quality") or {}
        ws.append(
            [
                tc["id"], tc["title"], tc["type"], tc["priority"],
                tc.get("severity"), tc.get("rank"), tc.get("traces_to"),
                _steps_text(tc["steps"]), tc["expected_result"],
                json.dumps(tc.get("test_data")) if tc.get("test_data") else "",
                q.get("clarity"), q.get("atomicity"), q.get("traceability"),
                q.get("duplicate"),
            ]
        )

    cov = wb.create_sheet("Coverage")
    cov.append(["Criterion", "Covered", "Covering Test Cases", "Gap Notes"])
    for c in pkg["coverage"]:
        cov.append(
            [
                c["criterion"], "yes" if c["covered"] else "no",
                ", ".join(str(i) for i in c["covering_test_case_ids"]),
                c["gap_notes"],
            ]
        )

    crit = wb.create_sheet("Acceptance Criteria")
    crit.append(["Label", "Text"])
    for c in pkg["acceptance_criteria"]:
        crit.append([c["label"], c["text"]])

    out = io.BytesIO()
    wb.save(out)
    return out.getvalue()


def to_pdf(pkg: dict) -> bytes:
    from fpdf import FPDF
    from fpdf.enums import XPos, YPos

    def clean(s: str) -> str:
        # fpdf core fonts are latin-1 only; drop unsupported chars.
        return (s or "").encode("latin-1", "replace").decode("latin-1")

    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    def line(text: str, h: float = 6) -> None:
        # multi_cell(w=0) defaults to new_x=RIGHT, which strands the cursor at
        # the right margin and makes the next full-width cell zero-width; force
        # the cursor back to the left margin on the next line every time.
        pdf.multi_cell(0, h, clean(text), new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    r = pkg["requirement"]
    pdf.set_font("Helvetica", "B", 16)
    line(f"Test Design Package - {r['title']}", 9)
    pdf.set_font("Helvetica", "", 10)
    line(f"Type: {r['type']} | Priority: {r['priority']}")
    pdf.ln(2)

    pdf.set_font("Helvetica", "B", 12)
    line("Acceptance Criteria", 8)
    pdf.set_font("Helvetica", "", 10)
    for c in pkg["acceptance_criteria"]:
        line(f"{c['label']}: {c['text']}")
    pdf.ln(2)

    pdf.set_font("Helvetica", "B", 12)
    line("Test Cases", 8)
    for tc in pkg["test_cases"]:
        pdf.set_font("Helvetica", "B", 11)
        line(tc["title"])
        pdf.set_font("Helvetica", "", 9)
        meta = f"{tc['type']} | priority {tc['priority']}"
        if tc.get("traces_to"):
            meta += f" | {tc['traces_to']}"
        line(meta, 5)
        for i, s in enumerate(tc["steps"]):
            line(f"  {i + 1}. {s}", 5)
        line(f"  Expected: {tc['expected_result']}", 5)
        if tc.get("test_data"):
            line(f"  Test data: {json.dumps(tc['test_data'])}", 5)
        pdf.ln(1)

    out = pdf.output()
    return bytes(out)


SERIALIZERS = {
    "json": to_json,
    "csv": to_csv,
    "md": to_markdown,
    "xlsx": to_xlsx,
    "pdf": to_pdf,
}


def serialize(pkg: dict, fmt: str) -> bytes:
    return SERIALIZERS[fmt](pkg)
