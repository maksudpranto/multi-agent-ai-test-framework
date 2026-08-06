from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models import Priority, RequirementStatus, RequirementType


class RequirementCreate(BaseModel):
    title: str
    raw_text: str
    req_type: RequirementType = RequirementType.user_story
    priority: Priority = Priority.medium
    status: RequirementStatus = RequirementStatus.draft


class RequirementUpdate(BaseModel):
    title: str | None = None
    raw_text: str | None = None
    req_type: RequirementType | None = None
    priority: Priority | None = None
    status: RequirementStatus | None = None


class RequirementOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    project_id: int
    module_id: int | None
    title: str
    raw_text: str
    req_type: RequirementType
    priority: Priority
    status: RequirementStatus
    source_filename: str | None
    created_at: datetime
