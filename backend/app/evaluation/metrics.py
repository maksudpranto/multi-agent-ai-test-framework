"""Per-run metrics, persisted as ExperimentMetric rows.

After a cell (one benchmark item under one condition) finishes, this computes
the numbers the thesis reports and writes one ExperimentMetric per metric so the
results dashboard is a query, not a recomputation. The headline metric is
``mutation_score`` — the fraction of the item's seeded bugs the generated suite
catches, produced by the Phase 1 fault-detection harness. The rest (coverage,
duplicate rate, debate rounds, suite size, tokens, latency) are secondary
descriptors of how each condition got there and what it cost.
"""
from __future__ import annotations

from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.evaluation.harness import materialize_inputs, score_suite
from app.models import (
    AgentExecution,
    BenchmarkItem,
    CoverageReport,
    DebateTurn,
    ExperimentMetric,
    PipelineRun,
    QualityReport,
    TestCase,
    TestCaseStatus,
)

# Metric-name constants (also the column keys the dashboard reads).
MUTATION_SCORE = "mutation_score"
SUITE_VALID = "suite_valid"
N_TEST_CASES = "n_test_cases"
COVERAGE_PCT = "coverage_pct"
QUALITY_SCORE = "quality_score"
DUPLICATE_RATE = "duplicate_rate"
ROUNDS_TO_CONSENSUS = "rounds_to_consensus"
N_INPUTS = "n_inputs"
MUTANTS_KILLED = "mutants_killed"
MUTANTS_TOTAL = "mutants_total"
TOKENS_TOTAL = "tokens_total"
LATENCY_MS_TOTAL = "latency_ms_total"
# Cost-effectiveness: seeded bugs caught per 1,000 tokens spent. The headline
# "is multi-agent worth the extra cost?" number — multi-agent detects more faults
# but spends more tokens, so faults-per-token is the honest trade-off measure.
FAULTS_PER_1K_TOKENS = "faults_per_1k_tokens"


def _current_test_cases(db: Session, run: PipelineRun) -> list[TestCase]:
    """Live suite for a run: leaf of each version chain, not rejected."""
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


def _suite_cases(cases: list[TestCase]) -> list[dict]:
    return [
        {
            "title": c.title,
            "steps": c.steps,
            "expected_result": c.expected_result,
            "test_data": c.test_data,
            "type": c.type,
        }
        for c in cases
    ]


def _fault_detection(
    db: Session,
    run: PipelineRun,
    item: BenchmarkItem,
    cases: list[TestCase],
    llm_service,
    model: str,
) -> tuple[dict[str, float], dict]:
    """Harvest the suite's inputs and score them against the item's mutants.
    Returns (scalar metrics, drill-down detail)."""
    mutants = [
        {"key": m.mutant_key, "code": m.code, "fault_type": m.fault_type}
        for m in item.mutants
    ]
    if not cases:
        detail = {
            "suite_valid": False, "materialized": False, "inputs": [],
            "n_usable_inputs": 0, "reason": "no_test_cases",
            "per_mutant": [{"key": m["key"], "fault_type": m["fault_type"],
                            "killed": False, "killed_by_input": None}
                           for m in mutants],
            "by_fault_type": _by_fault_type(
                [{"fault_type": m["fault_type"], "killed": False} for m in mutants]
            ),
        }
        return (
            {MUTATION_SCORE: 0.0, SUITE_VALID: 0.0, N_INPUTS: 0.0,
             MUTANTS_KILLED: 0.0, MUTANTS_TOTAL: float(len(mutants))},
            detail,
        )

    inputs, materialized = materialize_inputs(
        llm_service,
        signature=item.signature or item.entrypoint,
        params=item.params,
        canonical_inputs=item.canonical_inputs or [],
        suite_cases=_suite_cases(cases),
        model=model,
    )
    result = score_suite(
        reference_code=item.reference_code,
        mutants=mutants,
        entrypoint=item.entrypoint,
        inputs=inputs,
    )
    detail = {
        "suite_valid": result.suite_valid,
        "materialized": materialized,
        "inputs": result.inputs,
        "n_usable_inputs": result.n_usable_inputs,
        "per_mutant": result.per_mutant,
        "by_fault_type": _by_fault_type(result.per_mutant),
    }
    return (
        {
            MUTATION_SCORE: result.mutation_score,
            SUITE_VALID: 1.0 if result.suite_valid else 0.0,
            N_INPUTS: float(result.n_inputs),
            MUTANTS_KILLED: float(result.killed),
            MUTANTS_TOTAL: float(result.total),
        },
        detail,
    )


def _by_fault_type(per_mutant: list[dict]) -> dict[str, dict[str, int]]:
    """Group a run's per-mutant verdicts into {fault_type: {killed, total}}, so
    fault detection can later be aggregated by fault class across an experiment."""
    out: dict[str, dict[str, int]] = {}
    for m in per_mutant:
        ft = m.get("fault_type") or "unclassified"
        bucket = out.setdefault(ft, {"killed": 0, "total": 0})
        bucket["total"] += 1
        if m.get("killed"):
            bucket["killed"] += 1
    return out


def _coverage_pct(db: Session, run: PipelineRun) -> float | None:
    reports = list(
        db.scalars(
            select(CoverageReport).where(CoverageReport.pipeline_run_id == run.id)
        )
    )
    if not reports:
        return None
    covered = sum(1 for r in reports if r.covered)
    return round(100.0 * covered / len(reports), 2)


def _quality(db: Session, run: PipelineRun) -> tuple[float | None, float | None]:
    """(overall quality score, duplicate rate) from QualityReport rows."""
    reports = list(
        db.scalars(
            select(QualityReport).where(QualityReport.pipeline_run_id == run.id)
        )
    )
    if not reports:
        return None, None
    means = [
        ((r.clarity_score or 0.0) + (r.atomicity_score or 0.0) + (r.traceability_score or 0.0)) / 3.0
        for r in reports
    ]
    overall = round(sum(means) / len(reports), 3)
    dup_rate = round(sum(1 for r in reports if r.duplicate_flag) / len(reports), 3)
    return overall, dup_rate


def _rounds_to_consensus(db: Session, run: PipelineRun) -> float | None:
    max_round = db.scalar(
        select(func.max(DebateTurn.round)).where(
            DebateTurn.pipeline_run_id == run.id
        )
    )
    return float(max_round) if max_round else None


def _cost(db: Session, run: PipelineRun) -> tuple[float, float]:
    """(total tokens, total latency ms) summed over the run's agent executions."""
    tokens = db.scalar(
        select(
            func.coalesce(func.sum(AgentExecution.tokens_in), 0)
            + func.coalesce(func.sum(AgentExecution.tokens_out), 0)
        ).where(AgentExecution.pipeline_run_id == run.id)
    )
    latency = db.scalar(
        select(func.coalesce(func.sum(AgentExecution.latency_ms), 0)).where(
            AgentExecution.pipeline_run_id == run.id
        )
    )
    return float(tokens or 0), float(latency or 0)


def compute_run_metrics(
    db: Session,
    run: PipelineRun,
    item: BenchmarkItem,
    *,
    llm_service,
    model: str,
) -> dict[str, float]:
    """Compute all metrics for one finished cell and persist them as
    ExperimentMetric rows. Existing metric rows for the run are replaced so a
    re-scored cell does not accumulate duplicates. Returns the metric dict."""
    cases = _current_test_cases(db, run)

    metrics: dict[str, float] = {}
    fault_metrics, detail = _fault_detection(db, run, item, cases, llm_service, model)
    metrics.update(fault_metrics)
    metrics[N_TEST_CASES] = float(len(cases))
    # Stash the concrete drill-down detail on the run for the results screen.
    run.eval_detail = detail

    cov = _coverage_pct(db, run)
    if cov is not None:
        metrics[COVERAGE_PCT] = cov

    quality, dup_rate = _quality(db, run)
    if quality is not None:
        metrics[QUALITY_SCORE] = quality
    if dup_rate is not None:
        metrics[DUPLICATE_RATE] = dup_rate

    rounds = _rounds_to_consensus(db, run)
    if rounds is not None:
        metrics[ROUNDS_TO_CONSENSUS] = rounds

    tokens, latency = _cost(db, run)
    metrics[TOKENS_TOTAL] = tokens
    metrics[LATENCY_MS_TOTAL] = latency
    # Cost-effectiveness: bugs caught per 1,000 tokens. Only meaningful when the
    # oracle ran (suite_valid) and tokens were actually spent.
    if tokens > 0 and metrics.get(SUITE_VALID, 0.0) >= 1.0:
        metrics[FAULTS_PER_1K_TOKENS] = round(
            metrics.get(MUTANTS_KILLED, 0.0) / (tokens / 1000.0), 4
        )

    # Replace any prior metric rows for this run (idempotent re-scoring).
    db.query(ExperimentMetric).filter(
        ExperimentMetric.pipeline_run_id == run.id
    ).delete()
    for name, value in metrics.items():
        db.add(
            ExperimentMetric(
                experiment_id=run.experiment_id,
                pipeline_run_id=run.id,
                metric_name=name,
                metric_value=value,
            )
        )
    db.flush()
    return metrics
