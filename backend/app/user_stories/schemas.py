from datetime import datetime

from pydantic import BaseModel, ConfigDict


class UserStoryCreate(BaseModel):
    title: str
    raw_text: str


class UserStoryUpdate(BaseModel):
    title: str | None = None
    raw_text: str | None = None


class UserStoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    project_id: int
    title: str
    raw_text: str
    created_at: datetime
