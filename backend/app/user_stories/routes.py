from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.database import get_db
from app.models import Project, User, UserStory
from app.user_stories.schemas import (
    UserStoryCreate,
    UserStoryOut,
    UserStoryUpdate,
)

router = APIRouter(prefix="/projects/{project_id}/user-stories", tags=["user-stories"])


def _get_owned_project(project_id: int, user: User, db: Session) -> Project:
    project = db.get(Project, project_id)
    if project is None or project.owner_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Project not found"
        )
    return project


def _get_owned_story(
    project_id: int, story_id: int, user: User, db: Session
) -> UserStory:
    _get_owned_project(project_id, user, db)
    story = db.get(UserStory, story_id)
    if story is None or story.project_id != project_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User story not found"
        )
    return story


@router.get("", response_model=list[UserStoryOut])
def list_user_stories(
    project_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[UserStory]:
    _get_owned_project(project_id, user, db)
    return list(
        db.scalars(
            select(UserStory)
            .where(UserStory.project_id == project_id)
            .order_by(UserStory.created_at.desc())
        )
    )


@router.post("", response_model=UserStoryOut, status_code=status.HTTP_201_CREATED)
def create_user_story(
    project_id: int,
    payload: UserStoryCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> UserStory:
    _get_owned_project(project_id, user, db)
    story = UserStory(
        project_id=project_id, title=payload.title, raw_text=payload.raw_text
    )
    db.add(story)
    db.commit()
    db.refresh(story)
    return story


@router.get("/{story_id}", response_model=UserStoryOut)
def get_user_story(
    project_id: int,
    story_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> UserStory:
    return _get_owned_story(project_id, story_id, user, db)


@router.patch("/{story_id}", response_model=UserStoryOut)
def update_user_story(
    project_id: int,
    story_id: int,
    payload: UserStoryUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> UserStory:
    story = _get_owned_story(project_id, story_id, user, db)
    if payload.title is not None:
        story.title = payload.title
    if payload.raw_text is not None:
        story.raw_text = payload.raw_text
    db.commit()
    db.refresh(story)
    return story


@router.delete("/{story_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user_story(
    project_id: int,
    story_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> None:
    story = _get_owned_story(project_id, story_id, user, db)
    db.delete(story)
    db.commit()
