"""Experiment runner: execute a study cell by cell.

An experiment is a grid of (benchmark item x condition) cells. The runner walks
that grid, running each cell through the shared engine, scoring the resulting
suite against the item's seeded bugs, and persisting the metrics. It is:

  - **resumable** — a cell that already has a completed run with a mutation-score
    metric is skipped, so a crashed or half-spent-quota run can be re-invoked and
    only does the missing work;
  - **fault-isolating** — one cell raising (e.g. a provider hiccup) is recorded
    as a failed run and the grid continues;
  - **session-owning** — the background entrypoint opens and closes its own DB
    session, since it runs outside a request.

No agent behaviour is special-cased for experiments: single-LLM cells call the
same ``run_baseline`` the UI does, multi-agent cells call ``run_full_pipeline``
with the condition's ablation toggles. That is what keeps the comparison fair.
"""
from __future__ import annotations

import logging

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.benchmark.corpus import QUICK_SLUGS
from app.config import _PROVIDER_DEFAULT_MODEL, get_settings
from app.database import SessionLocal
from app.evaluation.conditions import Condition, resolve_conditions
from app.evaluation.metrics import MUTATION_SCORE, compute_run_metrics
from app.llm.service import service_for_provider
from app.models import (
    BenchmarkItem,
    Experiment,
    ExperimentMetric,
    ExperimentMode,
    PipelineRun,
    PipelineStage,
    RunStatus,
    utcnow,
)
from app.workflow.config import RunConfig
from app.workflow.engine import DefaultWorkflowEngine

logger = logging.getLogger("evaluation.runner")


def scoped_items(db: Session, experiment: Experiment) -> list[BenchmarkItem]:
    """The benchmark programs this experiment runs: all of them for a 'full'
    experiment, or the small representative subset for a 'quick' one. Ordered by
    id so the runner and the progress counter agree on the grid."""
    items = list(
        db.scalars(
            select(BenchmarkItem)
            .where(BenchmarkItem.dataset_id == experiment.dataset_id)
            .order_by(BenchmarkItem.id)
        )
    )
    if (experiment.scope or "full") == "quick":
        quick = set(QUICK_SLUGS)
        subset = [it for it in items if it.slug in quick]
        # Never let a stale/renamed subset silently run zero programs.
        if subset:
            return subset
    return items


class ExperimentRunner:
    """Runs one experiment's grid with a given engine + model."""

    def __init__(self, engine: DefaultWorkflowEngine, *, model: str):
        self.engine = engine
        self.model = model

    # -- cell-level ----------------------------------------------------------
    def _already_done(
        self, db: Session, experiment_id: int, requirement_id: int,
        condition_key: str, repetition: int,
    ) -> bool:
        run_id = db.scalar(
            select(PipelineRun.id)
            .where(
                PipelineRun.experiment_id == experiment_id,
                PipelineRun.requirement_id == requirement_id,
                PipelineRun.experiment_condition == condition_key,
                PipelineRun.repetition == repetition,
                PipelineRun.status == RunStatus.completed,
            )
            .order_by(PipelineRun.id.desc())
            .limit(1)
        )
        if run_id is None:
            return False
        # Guard against a completed run that was never scored.
        return db.scalar(
            select(ExperimentMetric.id).where(
                ExperimentMetric.pipeline_run_id == run_id,
                ExperimentMetric.metric_name == MUTATION_SCORE,
            ).limit(1)
        ) is not None

    def _run_cell(
        self,
        db: Session,
        experiment: Experiment,
        item: BenchmarkItem,
        condition: Condition,
        base_config: RunConfig,
        repetition: int,
    ) -> dict:
        requirement = item.requirement
        cfg = condition.apply(base_config)

        run = PipelineRun(
            requirement_id=requirement.id,
            experiment_id=experiment.id,
            experiment_condition=condition.key,
            repetition=repetition,
            mode=condition.mode,
            input_mode="requirement",
            current_stage=PipelineStage.test_generation,
            status=RunStatus.running,
        )
        db.add(run)
        db.commit()
        db.refresh(run)

        try:
            if condition.mode == ExperimentMode.single_llm:
                self.engine.run_baseline(
                    db, run, user_story=requirement.raw_text, config=cfg
                )
            else:
                self.engine.run_full_pipeline(
                    db, run, requirement=requirement, config=cfg
                )

            metrics = compute_run_metrics(
                db, run, item, llm_service=self.engine.llm, model=self.model
            )
            run.status = RunStatus.completed
            run.completed_at = utcnow()
            db.commit()
            logger.info(
                "cell done: exp=%s rep=%s item=%s cond=%s mutation_score=%.3f",
                experiment.id, repetition, item.slug, condition.key,
                metrics.get(MUTATION_SCORE, 0.0),
            )
            return {"ok": True, "metrics": metrics}
        except Exception as exc:  # noqa: BLE001 - isolate one cell's failure
            db.rollback()
            run = db.get(PipelineRun, run.id)
            if run is not None:
                run.status = RunStatus.failed
                db.commit()
            logger.exception(
                "cell FAILED: exp=%s rep=%s item=%s cond=%s: %s",
                experiment.id, repetition, item.slug, condition.key, exc,
            )
            return {"ok": False, "error": str(exc)}

    # -- experiment-level ----------------------------------------------------
    def run_experiment(self, db: Session, experiment_id: int) -> dict:
        experiment = db.get(Experiment, experiment_id)
        if experiment is None:
            raise ValueError(f"Experiment {experiment_id} not found")

        conditions = resolve_conditions(experiment.conditions)
        items = scoped_items(db, experiment)
        base_config = RunConfig.defaults()
        base_config.model = self.model

        repetitions = max(1, int(experiment.repetitions or 1))
        experiment.status = RunStatus.running
        experiment.completed_at = None
        db.commit()

        total = len(items) * len(conditions) * repetitions
        done = skipped = failed = 0
        logger.info(
            "experiment %s start: %d items x %d conditions x %d reps = %d cells",
            experiment_id, len(items), len(conditions), repetitions, total,
        )

        cancelled = False
        for rep in range(1, repetitions + 1):
            for item in items:
                for condition in conditions:
                    # Cooperative cancellation: a stop request flips the
                    # experiment's status in the DB; we check it between cells.
                    if self._is_cancelled(db, experiment_id):
                        cancelled = True
                        break
                    if self._already_done(
                        db, experiment_id, item.requirement_id, condition.key, rep
                    ):
                        skipped += 1
                        continue
                    outcome = self._run_cell(
                        db, experiment, item, condition, base_config, rep
                    )
                    if outcome["ok"]:
                        done += 1
                    else:
                        failed += 1
                if cancelled:
                    break
            if cancelled:
                break

        experiment.completed_at = utcnow()
        experiment.status = RunStatus.cancelled if cancelled else RunStatus.completed
        db.commit()
        summary = {
            "experiment_id": experiment_id,
            "total_cells": total,
            "completed": done,
            "skipped": skipped,
            "failed": failed,
            "cancelled": cancelled,
        }
        logger.info("experiment %s finished: %s", experiment_id, summary)
        return summary

    def _is_cancelled(self, db: Session, experiment_id: int) -> bool:
        """Fresh read of the experiment's status so a stop request made from
        another session is seen mid-run."""
        return db.scalar(
            select(Experiment.status).where(Experiment.id == experiment_id)
        ) == RunStatus.cancelled


def _resolve_engine_and_model(
    provider: str | None, model: str | None
) -> tuple[DefaultWorkflowEngine, str]:
    """Build the engine for the chosen provider and resolve the model name.
    Falls back to the configured default provider/model (mock in dev)."""
    settings = get_settings()
    provider = (provider or settings.llm_provider).lower().strip()
    resolved_model = model or _PROVIDER_DEFAULT_MODEL.get(
        provider, settings.effective_model
    )
    engine = DefaultWorkflowEngine(service_for_provider(provider))
    return engine, resolved_model


def run_experiment_task(
    experiment_id: int, provider: str | None = None, model: str | None = None
) -> dict:
    """Background entrypoint: owns its DB session so it can run detached from the
    request that scheduled it. On any fatal error the experiment is marked failed
    rather than left dangling in `running`."""
    db = SessionLocal()
    try:
        engine, resolved_model = _resolve_engine_and_model(provider, model)
        runner = ExperimentRunner(engine, model=resolved_model)
        return runner.run_experiment(db, experiment_id)
    except Exception:  # noqa: BLE001 - never leave the experiment stuck running
        logger.exception("experiment %s aborted", experiment_id)
        experiment = db.get(Experiment, experiment_id)
        if experiment is not None:
            experiment.status = RunStatus.failed
            db.commit()
        raise
    finally:
        db.close()


def experiment_progress(db: Session, experiment_id: int) -> dict:
    """Cheap progress snapshot for the status endpoint: how many cells are done
    out of the grid implied by the experiment's conditions x its benchmark
    items. Counts the latest completed run per cell."""
    experiment = db.get(Experiment, experiment_id)
    if experiment is None:
        return {"total": 0, "completed": 0, "failed": 0, "pct": 0.0}

    conditions = resolve_conditions(experiment.conditions)
    repetitions = max(1, int(experiment.repetitions or 1))
    n_items = len(scoped_items(db, experiment))
    total = n_items * len(conditions) * repetitions

    completed_cells = db.execute(
        select(
            PipelineRun.experiment_condition,
            PipelineRun.requirement_id,
            PipelineRun.repetition,
        )
        .where(
            PipelineRun.experiment_id == experiment_id,
            PipelineRun.status == RunStatus.completed,
        )
    ).all()
    completed = len({tuple(row) for row in completed_cells})
    failed = db.scalar(
        select(func.count(PipelineRun.id)).where(
            PipelineRun.experiment_id == experiment_id,
            PipelineRun.status == RunStatus.failed,
        )
    ) or 0
    return {
        "total": total,
        "completed": completed,
        "failed": failed,
        "pct": round(100.0 * completed / total, 1) if total else 0.0,
        "status": experiment.status.value if hasattr(experiment.status, "value") else experiment.status,
    }
