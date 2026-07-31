from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.database import get_db
from app.models import (
    AcceptanceCriterion,
    ExperimentMode,
    PipelineRun,
    PipelineStage,
    Project,
    RequirementAnalysis,
    RunStatus,
    User,
    UserStory,
    utcnow,
)
from app.pipeline.schemas import RequirementAnalysisResult
from app.workflow.config import RunConfig
from app.workflow.engine import DefaultWorkflowEngine

router = APIRouter(
    prefix="/projects/{project_id}/user-stories/{story_id}",
    tags=["pipeline"],
)


def _get_owned_story(
    project_id: int, story_id: int, user: User, db: Session
) -> UserStory:
    project = db.get(Project, project_id)
    if project is None or project.owner_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Project not found"
        )
    story = db.get(UserStory, story_id)
    if story is None or story.project_id != project_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User story not found"
        )
    return story


def _build_result(db: Session, run: PipelineRun, error: str | None):
    analysis = db.scalar(
        select(RequirementAnalysis).where(
            RequirementAnalysis.pipeline_run_id == run.id
        )
    )
    criteria = list(
        db.scalars(
            select(AcceptanceCriterion)
            .where(AcceptanceCriterion.pipeline_run_id == run.id)
            .order_by(AcceptanceCriterion.order)
        )
    )
    return RequirementAnalysisResult(
        run=run,
        analysis=analysis,
        acceptance_criteria=criteria,
        error=error,
    )


@router.post("/analyze", response_model=RequirementAnalysisResult)
def run_requirement_analysis(
    project_id: int,
    story_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> RequirementAnalysisResult:
    story = _get_owned_story(project_id, story_id, user, db)

    run = PipelineRun(
        user_story_id=story.id,
        mode=ExperimentMode.multi_agent,
        current_stage=PipelineStage.requirement_analysis,
        status=RunStatus.running,
    )
    db.add(run)
    db.commit()
    db.refresh(run)

    engine = DefaultWorkflowEngine()
    result = engine.run_stage(
        db,
        run,
        PipelineStage.requirement_analysis,
        inputs={"user_story": story.raw_text},
        config=RunConfig.defaults(),
    )

    run.status = RunStatus.completed if result.success else RunStatus.failed
    if result.success:
        run.completed_at = utcnow()
    db.commit()
    db.refresh(run)

    return _build_result(db, run, error=result.error)


@router.get("/latest-analysis", response_model=RequirementAnalysisResult | None)
def get_latest_analysis(
    project_id: int,
    story_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    story = _get_owned_story(project_id, story_id, user, db)
    run = db.scalar(
        select(PipelineRun)
        .where(PipelineRun.user_story_id == story.id)
        .order_by(PipelineRun.created_at.desc(), PipelineRun.id.desc())
    )
    if run is None:
        return None
    return _build_result(db, run, error=None)
