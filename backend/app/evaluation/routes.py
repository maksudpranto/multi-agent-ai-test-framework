"""Evaluation API: seed the benchmark, define + run experiments, read results.

Mirrors the existing pipeline routes — `Depends(get_db)` / `get_current_user`,
optional `ModelSelection` bodies validated against the free-model catalog, and
owner-scoped lookups. Running an experiment is fire-and-forget: the endpoint
returns 202 immediately and the study proceeds in a background task on its own DB
session (see `runner.run_experiment_task`), so a 24-cell study does not block the
request. Status/results are polled from the other endpoints.
"""
from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Body, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.config import _PROVIDER_DEFAULT_MODEL, get_settings
from app.database import get_db
from app.evaluation.conditions import CONDITIONS, resolve_conditions
from app.evaluation.runner import experiment_progress, run_experiment_task
from app.evaluation.schemas import (
    BenchmarkItemOut,
    BenchmarkSeedResult,
    ConditionOut,
    ExperimentCreate,
    ExperimentOut,
    ExperimentProgress,
    ExperimentRename,
    ExperimentStatusOut,
    RunAccepted,
)
from app.evaluation.stats import aggregate_experiment
from app.llm import catalog
from app.models import (
    AcceptanceCriterion,
    AgentExecution,
    BenchmarkItem,
    CoverageReport,
    Dataset,
    DebateTurn,
    Experiment,
    ExperimentMetric,
    ExperimentMode,
    ExportLog,
    PipelineRun,
    QualityReport,
    RequirementAnalysis,
    RunStatus,
    TestCase,
    TestCaseStatus,
    User,
    utcnow,
)

router = APIRouter(prefix="/evaluation", tags=["evaluation"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get_owned_experiment(experiment_id: int, user: User, db: Session) -> Experiment:
    experiment = db.get(Experiment, experiment_id)
    if experiment is None or experiment.owner_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Experiment not found"
        )
    return experiment


def _get_owned_dataset(dataset_id: int, user: User, db: Session) -> Dataset:
    dataset = db.get(Dataset, dataset_id)
    if dataset is None or dataset.owner_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Dataset not found"
        )
    return dataset


def _purge_runs(db: Session, experiment_id: int) -> None:
    """Delete an experiment's runs, metrics, and the artifacts of those runs
    (but not the experiment row). Shared by delete and by a fresh re-run."""
    run_ids = [
        r for r in db.scalars(
            select(PipelineRun.id).where(PipelineRun.experiment_id == experiment_id)
        )
    ]
    if run_ids:
        for model in (
            QualityReport, CoverageReport, DebateTurn, RequirementAnalysis,
            AgentExecution, ExportLog, TestCase, AcceptanceCriterion,
        ):
            db.query(model).filter(
                model.pipeline_run_id.in_(run_ids)
            ).delete(synchronize_session=False)
    db.query(ExperimentMetric).filter(
        ExperimentMetric.experiment_id == experiment_id
    ).delete(synchronize_session=False)
    db.query(PipelineRun).filter(
        PipelineRun.experiment_id == experiment_id
    ).delete(synchronize_session=False)


def _benchmark_dataset(user: User, db: Session) -> Dataset | None:
    return db.scalar(
        select(Dataset).where(
            Dataset.owner_id == user.id, Dataset.name == "Benchmark Suite"
        )
    )


def _exp_out(experiment: Experiment) -> ExperimentOut:
    return ExperimentOut(
        id=experiment.id,
        name=experiment.name,
        dataset_id=experiment.dataset_id,
        mode=experiment.mode.value if hasattr(experiment.mode, "value") else experiment.mode,
        status=experiment.status.value if hasattr(experiment.status, "value") else experiment.status,
        conditions=[c.key for c in resolve_conditions(experiment.conditions)],
        repetitions=experiment.repetitions or 1,
        created_at=experiment.created_at,
        completed_at=experiment.completed_at,
    )


def _resolve_selection(selection) -> tuple[str, str]:
    """Validate an optional {provider, model} body and return (provider, model).
    No selection -> the configured default backend (mock in dev). A given
    provider must be in the catalog and configured, matching the pipeline routes
    so the same UI model picker drives experiments."""
    settings = get_settings()
    if not selection or not (selection.provider or selection.model):
        provider = settings.llm_provider.lower().strip()
        return provider, settings.effective_model

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
    return provider, (model or _PROVIDER_DEFAULT_MODEL.get(provider, settings.effective_model))


# ---------------------------------------------------------------------------
# Catalog + benchmark
# ---------------------------------------------------------------------------


@router.get("/conditions", response_model=list[ConditionOut])
def list_conditions() -> list[ConditionOut]:
    """The experiment arms the UI offers as checkboxes."""
    return [
        ConditionOut(
            key=c.key, label=c.label, description=c.description, is_baseline=c.is_baseline
        )
        for c in CONDITIONS.values()
    ]


@router.post("/benchmark/seed", response_model=BenchmarkSeedResult)
def seed_benchmark_route(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> BenchmarkSeedResult:
    """Idempotently load the executable benchmark corpus for the current user."""
    from app.benchmark.seed import seed_benchmark

    info = seed_benchmark(db, user.id)
    return BenchmarkSeedResult(**{
        "dataset_id": info["dataset_id"],
        "project_id": info["project_id"],
        "n_items": info["n_items"],
        "created": info["created"],
        "refreshed": info["refreshed"],
    })


@router.get("/datasets/{dataset_id}/items", response_model=list[BenchmarkItemOut])
def list_benchmark_items(
    dataset_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[BenchmarkItemOut]:
    _get_owned_dataset(dataset_id, user, db)
    items = list(
        db.scalars(
            select(BenchmarkItem)
            .where(BenchmarkItem.dataset_id == dataset_id)
            .order_by(BenchmarkItem.id)
        )
    )
    return [
        BenchmarkItemOut(
            id=it.id,
            slug=it.slug,
            title=it.title,
            entrypoint=it.entrypoint,
            signature=it.signature,
            requirement_id=it.requirement_id,
            n_mutants=len(it.mutants),
        )
        for it in items
    ]


# ---------------------------------------------------------------------------
# Experiments
# ---------------------------------------------------------------------------


@router.get("/experiments", response_model=list[ExperimentOut])
def list_experiments(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[ExperimentOut]:
    experiments = list(
        db.scalars(
            select(Experiment)
            .where(Experiment.owner_id == user.id)
            .order_by(Experiment.created_at.desc(), Experiment.id.desc())
        )
    )
    return [_exp_out(e) for e in experiments]


@router.post("/experiments", response_model=ExperimentOut, status_code=status.HTTP_201_CREATED)
def create_experiment(
    payload: ExperimentCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ExperimentOut:
    name = payload.name.strip()
    if not name:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Experiment name is required",
        )

    # Default to the user's benchmark dataset when none is given.
    if payload.dataset_id is not None:
        dataset = _get_owned_dataset(payload.dataset_id, user, db)
    else:
        dataset = _benchmark_dataset(user, db)
        if dataset is None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Seed the benchmark before creating an experiment (POST /evaluation/benchmark/seed).",
            )

    if db.scalar(
        select(BenchmarkItem.id).where(BenchmarkItem.dataset_id == dataset.id).limit(1)
    ) is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="The chosen dataset has no benchmark items to evaluate.",
        )

    conditions = [c.key for c in resolve_conditions(payload.conditions)]
    repetitions = max(1, min(10, int(payload.repetitions or 1)))
    experiment = Experiment(
        owner_id=user.id,
        name=name,
        dataset_id=dataset.id,
        mode=ExperimentMode.multi_agent,
        conditions=conditions,
        repetitions=repetitions,
        status=RunStatus.pending,
    )
    db.add(experiment)
    db.commit()
    db.refresh(experiment)
    return _exp_out(experiment)


@router.post("/experiments/{experiment_id}/run", response_model=RunAccepted, status_code=status.HTTP_202_ACCEPTED)
def run_experiment_endpoint(
    experiment_id: int,
    background_tasks: BackgroundTasks,
    fresh: bool = False,
    selection=Body(default=None),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> RunAccepted:
    """Kick off, resume, or re-run the study in the background. Returns 202 at
    once; the grid runs cell by cell and is resumable, so a normal call after a
    partial run only does the missing work. Pass ``fresh=true`` to discard prior
    runs and re-run the whole grid from scratch (a true re-run)."""
    from app.evaluation.schemas import ModelSelection

    experiment = _get_owned_experiment(experiment_id, user, db)
    if experiment.status == RunStatus.running:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Experiment is already running.",
        )

    parsed = ModelSelection(**selection) if isinstance(selection, dict) else selection
    provider, model = _resolve_selection(parsed)

    if fresh:
        _purge_runs(db, experiment_id)
    experiment.status = RunStatus.running
    experiment.completed_at = None
    db.commit()

    background_tasks.add_task(run_experiment_task, experiment_id, provider, model)
    return RunAccepted(
        experiment_id=experiment_id,
        status="accepted",
        detail=f"Experiment running on {provider} / {model}.",
    )


@router.patch("/experiments/{experiment_id}", response_model=ExperimentOut)
def rename_experiment(
    experiment_id: int,
    payload: ExperimentRename,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ExperimentOut:
    experiment = _get_owned_experiment(experiment_id, user, db)
    name = payload.name.strip()
    if not name:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Experiment name cannot be empty",
        )
    experiment.name = name
    db.commit()
    db.refresh(experiment)
    return _exp_out(experiment)


@router.post("/experiments/{experiment_id}/stop", response_model=ExperimentOut)
def stop_experiment(
    experiment_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ExperimentOut:
    """Request cancellation. The background runner checks the status between
    cells and stops; already-finished cells are kept, so the partial results
    remain viewable."""
    experiment = _get_owned_experiment(experiment_id, user, db)
    if experiment.status not in (RunStatus.running, RunStatus.pending):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Experiment is not running.",
        )
    experiment.status = RunStatus.cancelled
    experiment.completed_at = utcnow()
    db.commit()
    db.refresh(experiment)
    return _exp_out(experiment)


@router.delete("/experiments/{experiment_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_experiment(
    experiment_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> None:
    """Delete an experiment and everything under it (runs, metrics, and the
    generated artifacts of those runs). Refuses while it is still running —
    stop it first."""
    experiment = _get_owned_experiment(experiment_id, user, db)
    if experiment.status == RunStatus.running:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Stop the experiment before deleting it.",
        )
    _purge_runs(db, experiment_id)
    db.delete(experiment)
    db.commit()


@router.get("/experiments/{experiment_id}", response_model=ExperimentStatusOut)
def get_experiment(
    experiment_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ExperimentStatusOut:
    experiment = _get_owned_experiment(experiment_id, user, db)
    return ExperimentStatusOut(
        experiment=_exp_out(experiment),
        progress=ExperimentProgress(**experiment_progress(db, experiment_id)),
    )


@router.get("/experiments/{experiment_id}/results")
def get_experiment_results(
    experiment_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    """Aggregated per-condition metrics + pairwise significance vs the baseline.
    Free-form dict so the dashboard can render new figures without a schema
    change."""
    experiment = _get_owned_experiment(experiment_id, user, db)
    result = aggregate_experiment(db, experiment_id)
    result["experiment"] = _exp_out(experiment).model_dump(mode="json")
    result["progress"] = experiment_progress(db, experiment_id)
    return result


@router.get("/experiments/{experiment_id}/items/{requirement_id}")
def get_item_drilldown(
    experiment_id: int,
    requirement_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    """Per-condition detail for one benchmark item: the metrics each condition
    scored and the suite it produced. This is the 'why' behind an aggregate."""
    _get_owned_experiment(experiment_id, user, db)
    item = db.scalar(
        select(BenchmarkItem).where(BenchmarkItem.requirement_id == requirement_id)
    )

    runs = list(
        db.scalars(
            select(PipelineRun).where(
                PipelineRun.experiment_id == experiment_id,
                PipelineRun.requirement_id == requirement_id,
            ).order_by(PipelineRun.id)
        )
    )
    # Latest run per condition.
    by_condition: dict[str, PipelineRun] = {}
    for run in runs:
        if run.experiment_condition:
            by_condition[run.experiment_condition] = run

    conditions_out = []
    for key, run in sorted(by_condition.items()):
        metric_rows = db.scalars(
            select(ExperimentMetric).where(
                ExperimentMetric.pipeline_run_id == run.id
            )
        )
        metrics = {r.metric_name: r.metric_value for r in metric_rows}
        cases = _current_cases(db, run)
        conditions_out.append({
            "condition": key,
            "label": CONDITIONS[key].label if key in CONDITIONS else key,
            "is_baseline": CONDITIONS[key].is_baseline if key in CONDITIONS else False,
            "run_id": run.id,
            "status": run.status.value if hasattr(run.status, "value") else run.status,
            "metrics": metrics,
            # Concrete per-bug verdict for this condition (which bug caught, and
            # the exact input that exposed it).
            "detail": run.eval_detail,
            "test_cases": [
                {"id": c.id, "title": c.title, "type": c.type, "steps": c.steps}
                for c in cases
            ],
        })

    return {
        "experiment_id": experiment_id,
        "requirement_id": requirement_id,
        "item": {
            "slug": item.slug if item else None,
            "title": item.title if item else None,
            "entrypoint": item.entrypoint if item else None,
            "signature": item.signature if item else None,
            "requirement_text": item.requirement.raw_text if item else None,
            "reference_code": item.reference_code if item else None,
            "mutants": [
                {"key": m.mutant_key, "description": m.description, "code": m.code}
                for m in (item.mutants if item else [])
            ],
        } if item else None,
        "conditions": conditions_out,
    }


def _current_cases(db: Session, run: PipelineRun) -> list[TestCase]:
    all_cases = list(
        db.scalars(
            select(TestCase)
            .where(TestCase.pipeline_run_id == run.id)
            .order_by(TestCase.id)
        )
    )
    superseded = {c.parent_test_case_id for c in all_cases if c.parent_test_case_id}
    return [
        c
        for c in all_cases
        if c.id not in superseded and c.status != TestCaseStatus.rejected
    ]
