from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.database import get_db
from app.models import Module, Project, Requirement, User
from app.modules.schemas import ModuleCreate, ModuleOut, ModuleUpdate

router = APIRouter(prefix="/projects/{project_id}/modules", tags=["modules"])


def _get_owned_project(project_id: int, user: User, db: Session) -> Project:
    project = db.get(Project, project_id)
    if project is None or project.owner_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Project not found"
        )
    return project


def _get_owned_module(
    project_id: int, module_id: int, user: User, db: Session
) -> Module:
    _get_owned_project(project_id, user, db)
    module = db.get(Module, module_id)
    if module is None or module.project_id != project_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Module not found"
        )
    return module


def _to_out(db: Session, module: Module) -> ModuleOut:
    count = db.scalar(
        select(func.count(Requirement.id)).where(
            Requirement.module_id == module.id
        )
    )
    out = ModuleOut.model_validate(module)
    out.requirement_count = count or 0
    return out


@router.get("", response_model=list[ModuleOut])
def list_modules(
    project_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[ModuleOut]:
    _get_owned_project(project_id, user, db)
    modules = db.scalars(
        select(Module)
        .where(Module.project_id == project_id)
        .order_by(Module.order, Module.created_at.desc())
    )
    return [_to_out(db, m) for m in modules]


@router.post("", response_model=ModuleOut, status_code=status.HTTP_201_CREATED)
def create_module(
    project_id: int,
    payload: ModuleCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ModuleOut:
    _get_owned_project(project_id, user, db)
    module = Module(
        project_id=project_id,
        name=payload.name,
        description=payload.description,
        status=payload.status,
        priority=payload.priority,
    )
    db.add(module)
    db.commit()
    db.refresh(module)
    return _to_out(db, module)


@router.get("/{module_id}", response_model=ModuleOut)
def get_module(
    project_id: int,
    module_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ModuleOut:
    module = _get_owned_module(project_id, module_id, user, db)
    return _to_out(db, module)


@router.patch("/{module_id}", response_model=ModuleOut)
def update_module(
    project_id: int,
    module_id: int,
    payload: ModuleUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ModuleOut:
    module = _get_owned_module(project_id, module_id, user, db)
    data = payload.model_dump(exclude_unset=True)
    for field, value in data.items():
        setattr(module, field, value)
    db.commit()
    db.refresh(module)
    return _to_out(db, module)


@router.delete("/{module_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_module(
    project_id: int,
    module_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> None:
    module = _get_owned_module(project_id, module_id, user, db)
    # Detach requirements rather than cascade-deleting them (a module delete
    # should not destroy requirement history + their pipeline runs).
    db.query(Requirement).filter(Requirement.module_id == module.id).update(
        {Requirement.module_id: None}
    )
    db.delete(module)
    db.commit()
