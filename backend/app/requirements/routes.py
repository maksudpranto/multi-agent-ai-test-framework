from pathlib import Path

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    UploadFile,
    status,
)
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.database import get_db
from app.models import (
    Priority,
    Project,
    Requirement,
    RequirementStatus,
    RequirementType,
    User,
)
from app.requirements.schemas import (
    RequirementCreate,
    RequirementOut,
    RequirementUpdate,
)

router = APIRouter(prefix="/projects/{project_id}", tags=["requirements"])


def _get_owned_project(project_id: int, user: User, db: Session) -> Project:
    project = db.get(Project, project_id)
    if project is None or project.owner_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Project not found"
        )
    return project


def _get_owned_requirement(
    project_id: int, requirement_id: int, user: User, db: Session
) -> Requirement:
    _get_owned_project(project_id, user, db)
    requirement = db.get(Requirement, requirement_id)
    if requirement is None or requirement.project_id != project_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Requirement not found"
        )
    return requirement


@router.get("/requirements", response_model=list[RequirementOut])
def list_requirements(
    project_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[Requirement]:
    """All requirements for a project (requirements live directly under a
    project — there is no module level)."""
    _get_owned_project(project_id, user, db)
    return list(
        db.scalars(
            select(Requirement)
            .where(Requirement.project_id == project_id)
            .order_by(Requirement.created_at.desc())
        )
    )


@router.post(
    "/requirements",
    response_model=RequirementOut,
    status_code=status.HTTP_201_CREATED,
)
def create_requirement(
    project_id: int,
    payload: RequirementCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Requirement:
    _get_owned_project(project_id, user, db)
    requirement = Requirement(
        project_id=project_id,
        title=payload.title,
        raw_text=payload.raw_text,
        req_type=payload.req_type,
        priority=payload.priority,
        status=payload.status,
    )
    db.add(requirement)
    db.commit()
    db.refresh(requirement)
    return requirement


@router.post(
    "/requirements/upload",
    response_model=RequirementOut,
    status_code=status.HTTP_201_CREATED,
)
def upload_requirement_document(
    project_id: int,
    file: UploadFile = File(...),
    title: str | None = Form(None),
    req_type: RequirementType = Form(RequirementType.feature_description),
    priority: Priority = Form(Priority.medium),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Requirement:
    """Create a requirement from an uploaded document. Text is extracted from
    UTF-8-decodable files (.txt/.md/.csv). Binary formats (PDF/DOCX) are accepted
    but stored with a placeholder note — richer parsing is a later enhancement."""
    _get_owned_project(project_id, user, db)
    raw_bytes = file.file.read()
    try:
        text = raw_bytes.decode("utf-8").strip()
    except UnicodeDecodeError:
        text = ""
    if not text:
        text = (
            f"[Uploaded document '{file.filename}' could not be text-extracted "
            "automatically. Paste or edit the requirement text here.]"
        )
    requirement = Requirement(
        project_id=project_id,
        title=title or Path(file.filename or "Uploaded requirement").stem,
        raw_text=text,
        req_type=req_type,
        priority=priority,
        status=RequirementStatus.draft,
        source_filename=file.filename,
    )
    db.add(requirement)
    db.commit()
    db.refresh(requirement)
    return requirement


@router.get("/requirements/{requirement_id}", response_model=RequirementOut)
def get_requirement(
    project_id: int,
    requirement_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Requirement:
    return _get_owned_requirement(project_id, requirement_id, user, db)


@router.patch("/requirements/{requirement_id}", response_model=RequirementOut)
def update_requirement(
    project_id: int,
    requirement_id: int,
    payload: RequirementUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Requirement:
    requirement = _get_owned_requirement(project_id, requirement_id, user, db)
    data = payload.model_dump(exclude_unset=True)
    for field, value in data.items():
        setattr(requirement, field, value)
    db.commit()
    db.refresh(requirement)
    return requirement


@router.delete(
    "/requirements/{requirement_id}", status_code=status.HTTP_204_NO_CONTENT
)
def delete_requirement(
    project_id: int,
    requirement_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> None:
    requirement = _get_owned_requirement(project_id, requirement_id, user, db)
    db.delete(requirement)
    db.commit()
