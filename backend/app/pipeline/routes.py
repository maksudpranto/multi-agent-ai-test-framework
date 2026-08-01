from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.database import get_db
from app.models import (
    AcceptanceCriterion,
    CoverageReport,
    DebateSpeaker,
    DebateTurn,
    ExperimentMode,
    PipelineRun,
    PipelineStage,
    Project,
    RequirementAnalysis,
    RunStatus,
    TestCase,
    TestCaseStatus,
    User,
    Requirement,
    utcnow,
)
from app.pipeline.schemas import (
    AcceptanceCriteriaIn,
    CoverageItemOut,
    CoverageResult,
    DebateResult,
    RequirementAnalysisResult,
    TestGenerationResult,
)
from app.workflow.config import RunConfig
from app.workflow.engine import DefaultWorkflowEngine

router = APIRouter(
    prefix="/projects/{project_id}/requirements/{requirement_id}",
    tags=["pipeline"],
)


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


def _current_test_cases(db: Session, run: PipelineRun) -> list[TestCase]:
    """The live suite for a run: leaf of each version chain (not superseded by a
    newer version) and not rejected. Ordered by rank when the Prioritizer has run,
    otherwise by id."""
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


def _build_test_generation_result(
    db: Session, run: PipelineRun, error: str | None
) -> TestGenerationResult:
    return TestGenerationResult(
        run=run, test_cases=_current_test_cases(db, run), error=error
    )


def _summary_from_turns(turns: list[DebateTurn]) -> dict:
    """Reconstruct the debate summary from the persisted transcript, so a page
    reload shows the same counters the live run returned."""
    reviewer_turns = [t for t in turns if t.speaker == DebateSpeaker.reviewer]
    consensus_turns = [t for t in turns if t.speaker == DebateSpeaker.consensus]
    total_findings = sum(
        len((t.content or {}).get("findings", [])) for t in reviewer_turns
    )
    revisions_made = sum(
        1
        for t in consensus_turns
        for r in (t.content or {}).get("resolutions", [])
        if r.get("decision") in ("revise", "add")
    )
    consensus_reached = False
    if reviewer_turns:
        last_reviewer = max(reviewer_turns, key=lambda t: (t.round, t.id))
        consensus_reached = not (last_reviewer.content or {}).get(
            "needs_revision", True
        )
    return {
        "rounds_used": max((t.round for t in turns), default=0),
        "consensus_reached": consensus_reached,
        "revisions_made": revisions_made,
        "total_findings": total_findings,
    }


def _build_debate_result(
    db: Session, run: PipelineRun, summary: dict, error: str | None
) -> DebateResult:
    turns = list(
        db.scalars(
            select(DebateTurn)
            .where(DebateTurn.pipeline_run_id == run.id)
            .order_by(DebateTurn.round, DebateTurn.id)
        )
    )
    test_cases = _current_test_cases(db, run)
    if not summary:
        summary = _summary_from_turns(turns)
    return DebateResult(
        run=run,
        rounds_used=summary.get("rounds_used", 0),
        consensus_reached=summary.get("consensus_reached", False),
        revisions_made=summary.get("revisions_made", 0),
        total_findings=summary.get("total_findings", 0),
        turns=turns,
        test_cases=test_cases,
        error=error,
    )


def _latest_run_with_test_cases(db: Session, requirement_id: int) -> PipelineRun | None:
    return db.scalar(
        select(PipelineRun)
        .join(TestCase, TestCase.pipeline_run_id == PipelineRun.id)
        .where(
            PipelineRun.requirement_id == requirement_id,
            PipelineRun.mode == ExperimentMode.multi_agent,
        )
        .order_by(PipelineRun.created_at.desc(), PipelineRun.id.desc())
    )


def _latest_run_with_criteria(db: Session, requirement_id: int) -> PipelineRun | None:
    """Latest multi-agent run that has acceptance criteria, regardless of how
    they were obtained (Analyzer-derived from a requirement, or user-supplied
    directly). This is the run test generation and the debate operate on."""
    return db.scalar(
        select(PipelineRun)
        .join(AcceptanceCriterion, AcceptanceCriterion.pipeline_run_id == PipelineRun.id)
        .where(
            PipelineRun.requirement_id == requirement_id,
            PipelineRun.mode == ExperimentMode.multi_agent,
        )
        .order_by(PipelineRun.created_at.desc(), PipelineRun.id.desc())
    )


@router.post("/analyze", response_model=RequirementAnalysisResult)
def run_requirement_analysis(
    project_id: int,
    requirement_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> RequirementAnalysisResult:
    requirement = _get_owned_requirement(project_id, requirement_id, user, db)

    run = PipelineRun(
        requirement_id=requirement.id,
        mode=ExperimentMode.multi_agent,
        input_mode="requirement",
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
        inputs={"user_story": requirement.raw_text},
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
    requirement_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    requirement = _get_owned_requirement(project_id, requirement_id, user, db)
    # Either input path (Analyzer-derived or user-supplied AC) surfaces here, so
    # select the latest multi-agent run that has criteria rather than requiring a
    # RequirementAnalysis row (AC-direct runs have none).
    run = _latest_run_with_criteria(db, requirement.id)
    if run is None:
        return None
    return _build_result(db, run, error=None)


@router.post("/acceptance-criteria", response_model=RequirementAnalysisResult)
def submit_acceptance_criteria(
    project_id: int,
    requirement_id: int,
    payload: AcceptanceCriteriaIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> RequirementAnalysisResult:
    """Alternative input path: the user supplies acceptance criteria directly,
    skipping requirement analysis. Creates a multi-agent run whose criteria come
    straight from the user, ready for test generation and the debate."""
    requirement = _get_owned_requirement(project_id, requirement_id, user, db)

    texts = [c.strip() for c in payload.criteria if c and c.strip()]
    if not texts:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="At least one non-empty acceptance criterion is required",
        )

    run = PipelineRun(
        requirement_id=requirement.id,
        mode=ExperimentMode.multi_agent,
        input_mode="acceptance_criteria",
        current_stage=PipelineStage.test_generation,
        status=RunStatus.completed,
        completed_at=utcnow(),
    )
    db.add(run)
    db.flush()
    for order, text in enumerate(texts):
        db.add(
            AcceptanceCriterion(pipeline_run_id=run.id, text=text, order=order)
        )
    db.commit()
    db.refresh(run)
    return _build_result(db, run, error=None)


@router.post("/generate-test-cases", response_model=TestGenerationResult)
def generate_test_cases(
    project_id: int,
    requirement_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> TestGenerationResult:
    requirement = _get_owned_requirement(project_id, requirement_id, user, db)
    run = _latest_run_with_criteria(db, requirement.id)
    if run is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Provide acceptance criteria (via analysis or directly) before generating test cases",
        )

    criteria = list(
        db.scalars(
            select(AcceptanceCriterion)
            .where(AcceptanceCriterion.pipeline_run_id == run.id)
            .order_by(AcceptanceCriterion.order)
        )
    )
    if not criteria:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="No acceptance criteria are available for test generation",
        )

    run.current_stage = PipelineStage.test_generation
    run.status = RunStatus.running
    run.completed_at = None
    db.commit()

    result = DefaultWorkflowEngine().run_stage(
        db,
        run,
        PipelineStage.test_generation,
        inputs={
            "user_story": requirement.raw_text,
            "acceptance_criteria": [
                {"id": criterion.id, "text": criterion.text} for criterion in criteria
            ],
        },
        config=RunConfig.defaults(),
    )
    run.status = RunStatus.completed if result.success else RunStatus.failed
    if result.success:
        run.completed_at = utcnow()
    db.commit()
    db.refresh(run)
    return _build_test_generation_result(db, run, error=result.error)


@router.get("/latest-test-cases", response_model=TestGenerationResult | None)
def get_latest_test_cases(
    project_id: int,
    requirement_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
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
        return None
    return _build_test_generation_result(db, run, error=None)


@router.post("/review-consensus", response_model=DebateResult)
def run_review_consensus(
    project_id: int,
    requirement_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> DebateResult:
    """Run the multi-agent Reviewer <-> Consensus debate over the latest set of
    generated test cases. This is the collaborative core of the framework."""
    requirement = _get_owned_requirement(project_id, requirement_id, user, db)
    run = _latest_run_with_test_cases(db, requirement.id)
    if run is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Generate test cases before running review & consensus",
        )

    criteria = list(
        db.scalars(
            select(AcceptanceCriterion)
            .where(AcceptanceCriterion.pipeline_run_id == run.id)
            .order_by(AcceptanceCriterion.order)
        )
    )

    run.status = RunStatus.running
    run.completed_at = None
    db.commit()

    summary = DefaultWorkflowEngine().run_debate(
        db,
        run,
        user_story=requirement.raw_text,
        acceptance_criteria=[{"id": c.id, "text": c.text} for c in criteria],
        config=RunConfig.defaults(),
    )

    run.status = RunStatus.completed
    run.completed_at = utcnow()
    db.commit()
    db.refresh(run)
    return _build_debate_result(db, run, summary, error=None)


@router.get("/latest-review-consensus", response_model=DebateResult | None)
def get_latest_review_consensus(
    project_id: int,
    requirement_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    requirement = _get_owned_requirement(project_id, requirement_id, user, db)
    run = db.scalar(
        select(PipelineRun)
        .join(DebateTurn, DebateTurn.pipeline_run_id == PipelineRun.id)
        .where(PipelineRun.requirement_id == requirement.id)
        .order_by(PipelineRun.created_at.desc(), PipelineRun.id.desc())
    )
    if run is None:
        return None
    return _build_debate_result(db, run, summary={}, error=None)


def _build_coverage_result(
    db: Session, run: PipelineRun, error: str | None
) -> CoverageResult:
    criteria = {
        c.id: c
        for c in db.scalars(
            select(AcceptanceCriterion).where(
                AcceptanceCriterion.pipeline_run_id == run.id
            )
        )
    }
    reports = list(
        db.scalars(
            select(CoverageReport)
            .where(CoverageReport.pipeline_run_id == run.id)
            .order_by(CoverageReport.id)
        )
    )
    items = [
        CoverageItemOut(
            acceptance_criterion_id=r.acceptance_criterion_id,
            criterion_text=criteria.get(r.acceptance_criterion_id).text
            if criteria.get(r.acceptance_criterion_id)
            else "",
            covered=r.covered,
            covering_test_case_ids=r.covering_test_case_ids or [],
            gap_notes=r.gap_notes,
        )
        for r in reports
    ]
    total = len(items)
    covered_count = sum(1 for i in items if i.covered)
    return CoverageResult(
        run=run,
        items=items,
        total=total,
        covered_count=covered_count,
        coverage_pct=round(100.0 * covered_count / total, 1) if total else 0.0,
        error=error,
    )


@router.post("/coverage", response_model=CoverageResult)
def run_coverage(
    project_id: int,
    requirement_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> CoverageResult:
    """Coverage / Validator agent: build the traceability matrix (deterministic)
    and judge whether each criterion's coverage is adequate (semantic)."""
    requirement = _get_owned_requirement(project_id, requirement_id, user, db)
    run = _latest_run_with_test_cases(db, requirement.id)
    if run is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Generate test cases before analysing coverage",
        )

    run.status = RunStatus.running
    run.completed_at = None
    db.commit()

    DefaultWorkflowEngine().run_coverage(
        db, run, user_story=requirement.raw_text, config=RunConfig.defaults()
    )

    run.status = RunStatus.completed
    run.completed_at = utcnow()
    db.commit()
    db.refresh(run)
    return _build_coverage_result(db, run, error=None)


@router.get("/latest-coverage", response_model=CoverageResult | None)
def get_latest_coverage(
    project_id: int,
    requirement_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    requirement = _get_owned_requirement(project_id, requirement_id, user, db)
    run = db.scalar(
        select(PipelineRun)
        .join(CoverageReport, CoverageReport.pipeline_run_id == PipelineRun.id)
        .where(PipelineRun.requirement_id == requirement.id)
        .order_by(PipelineRun.created_at.desc(), PipelineRun.id.desc())
    )
    if run is None:
        return None
    return _build_coverage_result(db, run, error=None)


@router.post("/prioritize", response_model=TestGenerationResult)
def run_prioritization(
    project_id: int,
    requirement_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> TestGenerationResult:
    """Prioritizer agent: rank the current multi-agent test suite by importance,
    assigning priority, severity, and a unique rank to each case (in place)."""
    requirement = _get_owned_requirement(project_id, requirement_id, user, db)
    run = _latest_run_with_test_cases(db, requirement.id)
    if run is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Generate test cases before prioritizing",
        )

    run.status = RunStatus.running
    run.completed_at = None
    db.commit()

    result = DefaultWorkflowEngine().run_prioritization(
        db, run, user_story=requirement.raw_text, config=RunConfig.defaults()
    )

    run.status = RunStatus.completed if result.success else RunStatus.failed
    if result.success:
        run.completed_at = utcnow()
    db.commit()
    db.refresh(run)
    return _build_test_generation_result(db, run, error=result.error)


@router.post("/baseline", response_model=TestGenerationResult)
def run_single_llm_baseline(
    project_id: int,
    requirement_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> TestGenerationResult:
    """Single-LLM baseline: one prompt turns the requirement straight into test cases.
    Runs in its own pipeline run (mode=single_llm) so it never mixes with the
    multi-agent artifacts and can be compared against them."""
    requirement = _get_owned_requirement(project_id, requirement_id, user, db)

    run = PipelineRun(
        requirement_id=requirement.id,
        mode=ExperimentMode.single_llm,
        current_stage=PipelineStage.test_generation,
        status=RunStatus.running,
    )
    db.add(run)
    db.commit()
    db.refresh(run)

    result = DefaultWorkflowEngine().run_baseline(
        db, run, user_story=requirement.raw_text, config=RunConfig.defaults()
    )

    run.status = RunStatus.completed if result.success else RunStatus.failed
    if result.success:
        run.completed_at = utcnow()
    db.commit()
    db.refresh(run)
    return _build_test_generation_result(db, run, error=result.error)


@router.get("/latest-baseline", response_model=TestGenerationResult | None)
def get_latest_baseline(
    project_id: int,
    requirement_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    requirement = _get_owned_requirement(project_id, requirement_id, user, db)
    run = db.scalar(
        select(PipelineRun)
        .where(
            PipelineRun.requirement_id == requirement.id,
            PipelineRun.mode == ExperimentMode.single_llm,
        )
        .order_by(PipelineRun.created_at.desc(), PipelineRun.id.desc())
    )
    if run is None:
        return None
    return _build_test_generation_result(db, run, error=None)
