from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models import ModuleStatus, Priority


class ModuleCreate(BaseModel):
    name: str
    description: str | None = None
    status: ModuleStatus = ModuleStatus.active
    priority: Priority = Priority.medium


class ModuleUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    status: ModuleStatus | None = None
    priority: Priority | None = None


class ModuleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    project_id: int
    name: str
    description: str | None
    status: ModuleStatus
    priority: Priority
    order: int
    created_at: datetime
    requirement_count: int = 0
