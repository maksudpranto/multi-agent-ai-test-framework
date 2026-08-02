import re

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.database import get_db
from app.export import service
from app.models import (
    ExperimentMode,
    ExportLog,
    PipelineRun,
    Project,
    Requirement,
    TestCase,
    User,
)

router = APIRouter(prefix="/projects/{project_id}/requirements/{requirement_id}", tags=["export"])


def _get_owned_requirement(
    project_id: int, requirement_id: int, user: User, db: Session
) -> Requirement:
    project = db.get(Project, project_id)
    if project is None or project.owner_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Project not found"
        )
    requirement = db.get(Requirement, requirement_id)
    if requirement is None or requirement.project_id != project_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Requirement not found"
        )
    return requirement


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", (text or "package").lower()).strip("-") or "package"


@router.get("/export")
def export_package(
    project_id: int,
    requirement_id: int,
    fmt: str = Query("json", description="json | csv | md | xlsx | pdf"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Response:
    """Export the complete test design package for the requirement's latest
    multi-agent run in the requested format."""
    if fmt not in service.FORMATS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported format '{fmt}'. Choose one of {list(service.FORMATS)}.",
        )
    requirement = _get_owned_requirement(project_id, requirement_id, user, db)
    run = db.scalar(
        select(PipelineRun)
        .join(TestCase, TestCase.pipeline_run_id == PipelineRun.id)
        .where(
            PipelineRun.requirement_id == requirement.id,
            PipelineRun.mode == ExperimentMode.multi_agent,
        )
        .order_by(PipelineRun.created_at.desc(), PipelineRun.id.desc())
    )
    if run is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Generate test cases before exporting",
        )

    package = service.build_package(db, run, requirement)
    payload = service.serialize(package, fmt)

    media_type, ext = service.FORMATS[fmt]
    db.add(
        ExportLog(
            pipeline_run_id=run.id,
            format=fmt,
            test_case_version_ids=[tc["id"] for tc in package["test_cases"]],
            file_path=None,
        )
    )
    db.commit()

    filename = f"{_slug(requirement.title)}-test-design.{ext}"
    return Response(
        content=payload,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
