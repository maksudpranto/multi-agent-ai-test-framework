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

SEED_PROMPTS: list[dict] = [
    {
        "stage": PipelineStage.requirement_analysis,
        "version": "v1",
        "template": REQUIREMENT_ANALYSIS_V1,
        "description": "Requirement analysis: user story -> structured spec.",
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
        db.add(PromptTemplate(**row, is_active=True))
        inserted += 1
    if inserted:
        db.commit()
    return inserted


def get_active_prompt(db: Session, stage: PipelineStage) -> PromptTemplate | None:
    """Newest active template for a stage."""
    return db.scalar(
        select(PromptTemplate)
        .where(PromptTemplate.stage == stage, PromptTemplate.is_active.is_(True))
        .order_by(PromptTemplate.created_at.desc(), PromptTemplate.id.desc())
    )
