from fastapi import APIRouter, Body, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.config import _PROVIDER_DEFAULT_MODEL, get_settings
from app.database import get_db
from app.llm import catalog
from app.llm.service import service_for_provider
from app.models import (
    AcceptanceCriterion,
    AgentExecution,
    CoverageReport,
    DebateSpeaker,
    DebateTurn,
    ExperimentMode,
    PipelineRun,
    PipelineStage,
    Project,
    QualityReport,
    RequirementAnalysis,
    RunStatus,
    TestCase,
    TestCaseStatus,
    User,
    Requirement,
    utcnow,
)
from app.pipeline.refine import refine_suite
from app.pipeline.schemas import (
    AcceptanceCriteriaIn,
    ModelSelection,
    CoverageItemOut,
    CoverageResult,
    DebateResult,
    QualityItemOut,
    QualityResult,
    RefineIn,
    RefineResult,
    RequirementAnalysisResult,
    TestCaseOut,
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


def _resolve_run(
    selection: ModelSelection | None,
) -> tuple[DefaultWorkflowEngine, RunConfig]:
    """Turn an optional {provider, model} body into the engine + config to run.

    No selection -> the configured default backend. A selection is validated
    against the free-model catalog and its provider must be configured, so the
    UI dropdown can switch models per run without any file edits."""
    settings = get_settings()
    config = RunConfig.defaults()
    if not selection or not (selection.provider or selection.model):
        return DefaultWorkflowEngine(), config

    provider = (selection.provider or settings.llm_provider).lower().strip()
    model = selection.model
    if catalog.find(provider, model) is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Unknown or unsupported model: {provider} / {model}",
        )
    if not catalog.provider_ready(provider, settings):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"{provider} is not configured — add its API key to the backend .env and restart.",
        )
    config.model = model or _PROVIDER_DEFAULT_MODEL.get(provider, config.model)
    try:
        engine = DefaultWorkflowEngine(service_for_provider(provider))
    except ValueError as exc:  # missing key surfaced by the provider builder
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    return engine, config


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
    selection: ModelSelection | None = Body(default=None),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> RequirementAnalysisResult:
    requirement = _get_owned_requirement(project_id, requirement_id, user, db)
    engine, config = _resolve_run(selection)

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

    result = engine.run_stage(
        db,
        run,
        PipelineStage.requirement_analysis,
        inputs={"user_story": requirement.raw_text},
        config=config,
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
    selection: ModelSelection | None = Body(default=None),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> TestGenerationResult:
    requirement = _get_owned_requirement(project_id, requirement_id, user, db)
    engine, config = _resolve_run(selection)
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

    result = engine.run_stage(
        db,
        run,
        PipelineStage.test_generation,
        inputs={
            "user_story": requirement.raw_text,
            "acceptance_criteria": [
                {"id": criterion.id, "text": criterion.text} for criterion in criteria
            ],
        },
        config=config,
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


@router.post("/refine-test-cases", response_model=RefineResult)
def refine_test_cases(
    project_id: int,
    requirement_id: int,
    payload: RefineIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> RefineResult:
    """Human-in-the-loop: apply a user's suggestion to the current suite when it
    is a valid, in-scope change; otherwise return a reason and leave it unchanged."""
    requirement = _get_owned_requirement(project_id, requirement_id, user, db)
    suggestion = (payload.suggestion or "").strip()
    if not suggestion:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Enter a suggestion to apply.",
        )

    run = _latest_run_with_test_cases(db, requirement.id)
    if run is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Generate a test suite before suggesting changes.",
        )

    engine, config = _resolve_run(payload)

    # The deterministic mock backend can't reason about a free-text suggestion.
    provider = (payload.provider or get_settings().llm_provider).lower().strip()
    if provider == "mock":
        cases = _current_test_cases(db, run)
        return RefineResult(
            applied=False,
            reason="Suggestions need a real AI model — pick Gemini or Groq in the "
            "model selector above (the offline mock can't evaluate them).",
            test_cases=cases,
        )

    criteria = list(
        db.scalars(
            select(AcceptanceCriterion)
            .where(AcceptanceCriterion.pipeline_run_id == run.id)
            .order_by(AcceptanceCriterion.order)
        )
    )
    cases = _current_test_cases(db, run)

    outcome = refine_suite(
        db=db,
        run=run,
        requirement_text=requirement.raw_text,
        criteria=criteria,
        cases=cases,
        suggestion=suggestion,
        service=engine.llm,
        model=config.model,
    )
    return RefineResult(
        applied=outcome["applied"],
        reason=outcome["reason"],
        test_cases=_current_test_cases(db, run),
    )


@router.post("/review-consensus", response_model=DebateResult)
def run_review_consensus(
    project_id: int,
    requirement_id: int,
    selection: ModelSelection | None = Body(default=None),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> DebateResult:
    """Run the multi-agent Reviewer <-> Consensus debate over the latest set of
    generated test cases. This is the collaborative core of the framework."""
    requirement = _get_owned_requirement(project_id, requirement_id, user, db)
    engine, config = _resolve_run(selection)
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

    summary = engine.run_debate(
        db,
        run,
        user_story=requirement.raw_text,
        acceptance_criteria=[{"id": c.id, "text": c.text} for c in criteria],
        config=config,
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
    selection: ModelSelection | None = Body(default=None),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> CoverageResult:
    """Coverage / Validator agent: build the traceability matrix (deterministic)
    and judge whether each criterion's coverage is adequate (semantic)."""
    requirement = _get_owned_requirement(project_id, requirement_id, user, db)
    engine, config = _resolve_run(selection)
    run = _latest_run_with_test_cases(db, requirement.id)
    if run is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Generate test cases before analysing coverage",
        )

    run.status = RunStatus.running
    run.completed_at = None
    db.commit()

    engine.run_coverage(
        db, run, user_story=requirement.raw_text, config=config
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


def _build_quality_result(
    db: Session, run: PipelineRun, error: str | None
) -> QualityResult:
    titles = {
        c.id: c.title
        for c in db.scalars(
            select(TestCase).where(TestCase.pipeline_run_id == run.id)
        )
    }
    reports = list(
        db.scalars(
            select(QualityReport)
            .where(QualityReport.pipeline_run_id == run.id)
            .order_by(QualityReport.id)
        )
    )
    items = [
        QualityItemOut(
            test_case_id=r.test_case_id,
            title=titles.get(r.test_case_id, ""),
            clarity_score=r.clarity_score,
            atomicity_score=r.atomicity_score,
            traceability_score=r.traceability_score,
            duplicate_flag=r.duplicate_flag,
            notes=r.notes,
        )
        for r in reports
    ]
    total = len(items)
    means = [
        ((i.clarity_score or 0) + (i.atomicity_score or 0) + (i.traceability_score or 0)) / 3.0
        for i in items
    ]
    return QualityResult(
        run=run,
        items=items,
        total=total,
        overall_score=round(sum(means) / total, 3) if total else 0.0,
        duplicate_count=sum(1 for i in items if i.duplicate_flag),
        error=error,
    )


@router.post("/quality", response_model=QualityResult)
def run_quality(
    project_id: int,
    requirement_id: int,
    selection: ModelSelection | None = Body(default=None),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> QualityResult:
    """Quality agent: score each current test case on clarity, atomicity, and
    traceability, and flag duplicates — the thesis's Quality Report."""
    requirement = _get_owned_requirement(project_id, requirement_id, user, db)
    engine, config = _resolve_run(selection)
    run = _latest_run_with_test_cases(db, requirement.id)
    if run is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Generate test cases before evaluating quality",
        )

    run.status = RunStatus.running
    run.completed_at = None
    db.commit()

    engine.run_quality(
        db, run, user_story=requirement.raw_text, config=config
    )

    run.status = RunStatus.completed
    run.completed_at = utcnow()
    db.commit()
    db.refresh(run)
    return _build_quality_result(db, run, error=None)


@router.get("/latest-quality", response_model=QualityResult | None)
def get_latest_quality(
    project_id: int,
    requirement_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    requirement = _get_owned_requirement(project_id, requirement_id, user, db)
    run = db.scalar(
        select(PipelineRun)
        .join(QualityReport, QualityReport.pipeline_run_id == PipelineRun.id)
        .where(PipelineRun.requirement_id == requirement.id)
        .order_by(PipelineRun.created_at.desc(), PipelineRun.id.desc())
    )
    if run is None:
        return None
    return _build_quality_result(db, run, error=None)


@router.post("/prioritize", response_model=TestGenerationResult)
def run_prioritization(
    project_id: int,
    requirement_id: int,
    selection: ModelSelection | None = Body(default=None),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> TestGenerationResult:
    """Prioritizer agent: rank the current multi-agent test suite by importance,
    assigning priority, severity, and a unique rank to each case (in place)."""
    requirement = _get_owned_requirement(project_id, requirement_id, user, db)
    engine, config = _resolve_run(selection)
    run = _latest_run_with_test_cases(db, requirement.id)
    if run is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Generate test cases before prioritizing",
        )

    run.status = RunStatus.running
    run.completed_at = None
    db.commit()

    result = engine.run_prioritization(
        db, run, user_story=requirement.raw_text, config=config
    )

    run.status = RunStatus.completed if result.success else RunStatus.failed
    if result.success:
        run.completed_at = utcnow()
    db.commit()
    db.refresh(run)
    return _build_test_generation_result(db, run, error=result.error)


@router.post("/test-cases/{test_case_id}/sample-data", response_model=TestCaseOut)
def generate_sample_data(
    project_id: int,
    requirement_id: int,
    test_case_id: int,
    selection: ModelSelection | None = Body(default=None),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> TestCase:
    """Test Data agent: generate concrete sample data for one test case, on
    demand, and store it on the case. Used from the test-case details view."""
    requirement = _get_owned_requirement(project_id, requirement_id, user, db)
    test_case = db.get(TestCase, test_case_id)
    if test_case is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Test case not found")
    run = db.get(PipelineRun, test_case.pipeline_run_id)
    if run is None or run.requirement_id != requirement.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Test case not found")

    engine, config = _resolve_run(selection)
    result = engine.run_test_data(
        db, run, test_case=test_case, user_story=requirement.raw_text, config=config
    )
    if not result.success:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=result.error or "Test data generation failed",
        )
    test_case.test_data = result.output["test_data"]
    db.commit()
    db.refresh(test_case)
    return test_case


@router.post("/orchestrate")
def orchestrate(
    project_id: int,
    requirement_id: int,
    selection: ModelSelection | None = Body(default=None),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    """Agentic run: the Orchestrator's planner drives the specialist agents to a
    goal under guardrails, in a fresh multi-agent run. Returns the decision
    trace (who acted and why) plus the resulting coverage/quality/suite."""
    requirement = _get_owned_requirement(project_id, requirement_id, user, db)
    engine, config = _resolve_run(selection)

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

    summary = engine.run_orchestration(
        db,
        run,
        requirement=requirement,
        config=config,
        goal={"coverage_target": 100, "max_steps": 10},
    )

    run.status = RunStatus.completed
    run.completed_at = utcnow()
    db.commit()
    db.refresh(run)

    executions = list(
        db.scalars(
            select(AgentExecution)
            .where(AgentExecution.pipeline_run_id == run.id)
            .order_by(AgentExecution.id)
        )
    )
    trace = []
    for e in executions:
        stage = e.stage.value if hasattr(e.stage, "value") else e.stage
        out = e.raw_output or {}
        is_plan = stage == "planning"
        trace.append(
            {
                "stage": stage,
                "attempt": e.attempt_no,
                "action": out.get("action") if is_plan else None,
                "rationale": e.reasoning if is_plan else None,
                "planner_fallback": out.get("planner_fallback") if is_plan else None,
                "status": e.status.value if hasattr(e.status, "value") else e.status,
            }
        )

    coverage = _build_coverage_result(db, run, None)
    quality = _build_quality_result(db, run, None)
    return {
        "run_id": run.id,
        "steps_used": summary["steps_used"],
        "decisions": summary["decisions"],
        "final_state": summary["final_state"],
        "trace": trace,
        "coverage_pct": coverage.coverage_pct,
        "quality_score": quality.overall_score,
        "test_case_count": len(_current_test_cases(db, run)),
    }


@router.post("/baseline", response_model=TestGenerationResult)
def run_single_llm_baseline(
    project_id: int,
    requirement_id: int,
    selection: ModelSelection | None = Body(default=None),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> TestGenerationResult:
    """Single-LLM baseline: one prompt turns the requirement straight into test cases.
    Runs in its own pipeline run (mode=single_llm) so it never mixes with the
    multi-agent artifacts and can be compared against them."""
    requirement = _get_owned_requirement(project_id, requirement_id, user, db)
    engine, config = _resolve_run(selection)

    run = PipelineRun(
        requirement_id=requirement.id,
        mode=ExperimentMode.single_llm,
        current_stage=PipelineStage.test_generation,
        status=RunStatus.running,
    )
    db.add(run)
    db.commit()
    db.refresh(run)

    result = engine.run_baseline(
        db, run, user_story=requirement.raw_text, config=config
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
