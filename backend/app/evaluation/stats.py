"""Statistics for the fault-based comparison — standard-library only.

The thesis claim is not "multi-agent looks better"; it is "multi-agent detects
significantly more faults than the baseline." That requires a paired significance
test. We use the **Wilcoxon signed-rank test** (non-parametric, paired by
benchmark item — appropriate for bounded mutation scores over a small sample)
with a normal approximation (tie- and continuity-corrected) computed from
``math.erf``, plus paired effect sizes (Cohen's dz, rank-biserial). No scipy /
numpy — deliberately, to stay robust on this Python 3.14 venv; an optional
``scipy`` path can be added later for exact small-n p-values.
"""
from __future__ import annotations

import math
from statistics import fmean, median, pstdev, stdev
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.evaluation import metrics as M
from app.evaluation.conditions import BASELINE_KEY, CONDITIONS
from app.models import ExperimentMetric, PipelineRun, RunStatus


# ---------------------------------------------------------------------------
# Pure statistics (operate on plain lists)
# ---------------------------------------------------------------------------


def _phi(z: float) -> float:
    """Standard-normal CDF via the error function."""
    return 0.5 * (1.0 + math.erf(z / math.sqrt(2.0)))


def describe(values: list[float]) -> dict[str, float]:
    """n / mean / sample-std / median / min / max for a metric column."""
    n = len(values)
    if n == 0:
        return {"n": 0, "mean": 0.0, "std": 0.0, "median": 0.0, "min": 0.0, "max": 0.0}
    return {
        "n": n,
        "mean": round(fmean(values), 4),
        "std": round(stdev(values), 4) if n > 1 else 0.0,
        "median": round(median(values), 4),
        "min": round(min(values), 4),
        "max": round(max(values), 4),
    }


def _ranks(values: list[float]) -> list[float]:
    """Average ('fractional') ranks, so tied magnitudes share their mean rank."""
    order = sorted(range(len(values)), key=lambda i: values[i])
    ranks = [0.0] * len(values)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and values[order[j + 1]] == values[order[i]]:
            j += 1
        avg = (i + j) / 2.0 + 1.0  # ranks are 1-based
        for k in range(i, j + 1):
            ranks[order[k]] = avg
        i = j + 1
    return ranks


def wilcoxon_signed_rank(x: list[float], y: list[float]) -> dict[str, Any]:
    """Paired Wilcoxon signed-rank test, two-sided, normal approximation.

    ``x`` and ``y`` are paired samples (x[i], y[i] the same benchmark item under
    two conditions). Returns the W+ statistic, z, two-sided p-value, and the
    number of non-zero pairs the test is based on. All-zero differences (the two
    conditions tied on every item) yield p=1.0."""
    diffs = [a - b for a, b in zip(x, y)]
    nonzero = [d for d in diffs if d != 0.0]
    n = len(nonzero)
    if n == 0:
        return {"statistic": 0.0, "z": 0.0, "p_value": 1.0, "n": 0}

    ranks = _ranks([abs(d) for d in nonzero])
    w_plus = sum(r for d, r in zip(nonzero, ranks) if d > 0)
    w_minus = sum(r for d, r in zip(nonzero, ranks) if d < 0)

    mean_w = n * (n + 1) / 4.0
    var_w = n * (n + 1) * (2 * n + 1) / 24.0

    # Tie correction: subtract sum((t^3 - t) / 48) over groups of tied |d|.
    counts: dict[float, int] = {}
    for d in nonzero:
        counts[abs(d)] = counts.get(abs(d), 0) + 1
    var_w -= sum((t**3 - t) for t in counts.values() if t > 1) / 48.0

    if var_w <= 0:
        return {"statistic": round(w_plus, 4), "z": 0.0, "p_value": 1.0, "n": n}

    # Continuity correction pulls the numerator toward 0 by 0.5.
    num = w_plus - mean_w
    num -= math.copysign(0.5, num) if num != 0 else 0.0
    z = num / math.sqrt(var_w)
    p = 2.0 * (1.0 - _phi(abs(z)))
    p = max(0.0, min(1.0, p))
    return {
        "statistic": round(w_plus, 4),
        "w_minus": round(w_minus, 4),
        "z": round(z, 4),
        "p_value": round(p, 5),
        "n": n,
    }


def cohens_dz(x: list[float], y: list[float]) -> float | None:
    """Paired effect size: mean difference over the SD of the differences."""
    diffs = [a - b for a, b in zip(x, y)]
    if len(diffs) < 2:
        return None
    sd = stdev(diffs)
    if sd == 0.0:
        return 0.0 if fmean(diffs) == 0.0 else math.copysign(float("inf"), fmean(diffs))
    return round(fmean(diffs) / sd, 4)


def rank_biserial(x: list[float], y: list[float]) -> float | None:
    """Rank-biserial correlation for the paired Wilcoxon: (W+ - W-)/(W+ + W-),
    in [-1, 1]. Positive means x tends to exceed y."""
    diffs = [a - b for a, b in zip(x, y)]
    nonzero = [d for d in diffs if d != 0.0]
    if not nonzero:
        return 0.0
    ranks = _ranks([abs(d) for d in nonzero])
    w_plus = sum(r for d, r in zip(nonzero, ranks) if d > 0)
    w_minus = sum(r for d, r in zip(nonzero, ranks) if d < 0)
    total = w_plus + w_minus
    return round((w_plus - w_minus) / total, 4) if total else 0.0


# ---------------------------------------------------------------------------
# Experiment-level aggregation (reads the DB)
# ---------------------------------------------------------------------------

# Metrics summarised per condition on the results screen.
_SUMMARY_METRICS = [
    M.MUTATION_SCORE,
    M.COVERAGE_PCT,
    M.QUALITY_SCORE,
    M.DUPLICATE_RATE,
    M.N_TEST_CASES,
    M.ROUNDS_TO_CONSENSUS,
    M.TOKENS_TOTAL,
    M.LATENCY_MS_TOTAL,
    M.FAULTS_PER_1K_TOKENS,
]


def _cells(
    db: Session, experiment_id: int
) -> dict[tuple[str, int, int], dict[str, float]]:
    """Map (condition_key, requirement_id, repetition) -> {metric: value} for the
    latest completed run of each cell."""
    runs = list(
        db.scalars(
            select(PipelineRun)
            .where(
                PipelineRun.experiment_id == experiment_id,
                PipelineRun.status == RunStatus.completed,
                PipelineRun.experiment_condition.is_not(None),
            )
            .order_by(PipelineRun.id)
        )
    )
    run_by_cell: dict[tuple[str, int, int], PipelineRun] = {}
    for run in runs:
        run_by_cell[
            (run.experiment_condition, run.requirement_id, run.repetition or 1)
        ] = run

    if not run_by_cell:
        return {}

    run_ids = [r.id for r in run_by_cell.values()]
    metric_rows = list(
        db.scalars(
            select(ExperimentMetric).where(
                ExperimentMetric.pipeline_run_id.in_(run_ids)
            )
        )
    )
    by_run: dict[int, dict[str, float]] = {}
    for row in metric_rows:
        by_run.setdefault(row.pipeline_run_id, {})[row.metric_name] = row.metric_value

    return {cell: by_run.get(run.id, {}) for cell, run in run_by_cell.items()}


def fault_type_breakdown(db: Session, experiment_id: int) -> dict[str, Any]:
    """Fault detection broken down by fault class, per condition.

    Reads each completed run's ``eval_detail['by_fault_type']`` (killed/total per
    fault class, written by the harness) and sums it over every item and
    repetition of each condition. The result answers a sharper question than the
    single mutation score: *which kinds of bug* does each arm catch — e.g. does
    the multi-agent suite close the boundary/edge-case gap the baseline leaves
    open?"""
    from app.benchmark.corpus import FAULT_TAXONOMY  # local: avoid import cycle

    runs = list(
        db.scalars(
            select(PipelineRun).where(
                PipelineRun.experiment_id == experiment_id,
                PipelineRun.status == RunStatus.completed,
                PipelineRun.experiment_condition.is_not(None),
            )
        )
    )
    # condition -> fault_type -> {killed, total}
    agg: dict[str, dict[str, dict[str, int]]] = {}
    for run in runs:
        detail = run.eval_detail or {}
        # Only count cells where the oracle actually ran.
        if not detail.get("suite_valid"):
            continue
        by_ft = detail.get("by_fault_type") or {}
        cond = agg.setdefault(run.experiment_condition, {})
        for ft, cnt in by_ft.items():
            bucket = cond.setdefault(ft, {"killed": 0, "total": 0})
            bucket["killed"] += int(cnt.get("killed", 0))
            bucket["total"] += int(cnt.get("total", 0))

    by_condition: dict[str, dict[str, Any]] = {}
    for cond_key, per_ft in agg.items():
        rows = {}
        for ft, c in per_ft.items():
            total = c["total"]
            rows[ft] = {
                "killed": c["killed"],
                "total": total,
                "rate": round(c["killed"] / total, 4) if total else None,
            }
        by_condition[cond_key] = rows

    return {
        "legend": [dict(f) for f in FAULT_TAXONOMY],
        "by_condition": by_condition,
    }


def _valid_score(values: dict[str, float]) -> bool:
    """A cell counts toward fault-detection stats only if the reference oracle
    ran on at least one harvested input (suite_valid == 1)."""
    return values.get(M.SUITE_VALID, 0.0) >= 1.0


def _item_mean(
    cells: dict, key: str, rid: int, reps: list[int], metric: str, valid_only: bool
) -> float | None:
    """Mean of a metric for one (condition, item) cell across its repetitions.
    Averaging across repeats is what makes the comparison robust to LLM
    run-to-run noise."""
    vals = []
    for rep in reps:
        v = cells.get((key, rid, rep))
        if v is None or metric not in v:
            continue
        if valid_only and not _valid_score(v):
            continue
        vals.append(v[metric])
    return fmean(vals) if vals else None


def aggregate_experiment(db: Session, experiment_id: int) -> dict[str, Any]:
    """Per-condition summaries + pairwise significance vs the baseline, averaged
    across repetitions with a reported run-to-run spread.

    Each (condition, item) score is first averaged over the experiment's
    repetitions (robust to LLM non-determinism); the paired Wilcoxon test then
    runs on those per-item means. Per condition we also report the standard
    deviation of the whole-suite score across repetitions — the reproducibility
    measure."""
    cells = _cells(db, experiment_id)
    conditions_present = sorted({key for (key, _r, _rep) in cells})
    requirement_ids = sorted({rid for (_k, rid, _rep) in cells})
    reps_present = sorted({rep for (_k, _r, rep) in cells})

    condition_out: list[dict[str, Any]] = []
    for key in conditions_present:
        cond = CONDITIONS.get(key)
        # Per-item mean fault score across repetitions (valid cells only).
        item_scores = [
            m for rid in requirement_ids
            if (m := _item_mean(cells, key, rid, reps_present, M.MUTATION_SCORE, True)) is not None
        ]
        summary: dict[str, dict] = {M.MUTATION_SCORE: describe(item_scores)}
        for name in _SUMMARY_METRICS:
            if name == M.MUTATION_SCORE:
                continue
            col = [
                m for rid in requirement_ids
                if (m := _item_mean(cells, key, rid, reps_present, name, False)) is not None
            ]
            if col:
                summary[name] = describe(col)

        # Run-to-run spread: whole-suite mean per repetition, std across reps.
        rep_means = []
        for rep in reps_present:
            per_rep = [
                v[M.MUTATION_SCORE]
                for rid in requirement_ids
                if (v := cells.get((key, rid, rep))) is not None
                and _valid_score(v) and M.MUTATION_SCORE in v
            ]
            if per_rep:
                rep_means.append(fmean(per_rep))
        run_to_run_std = round(stdev(rep_means), 4) if len(rep_means) > 1 else 0.0

        n_runs = sum(1 for (k, _r, _rep) in cells if k == key)
        condition_out.append({
            "key": key,
            "label": cond.label if cond else key,
            "description": cond.description if cond else "",
            "is_baseline": bool(cond and cond.is_baseline),
            "n_runs": n_runs,
            "n_valid": len(item_scores),
            "n_reps": len(rep_means),
            "run_to_run_std": run_to_run_std,
            "rep_means": [round(x, 4) for x in rep_means],
            "metrics": summary,
        })

    # Pairwise comparisons vs the baseline, on the per-item means.
    comparisons: list[dict[str, Any]] = []
    baseline_present = BASELINE_KEY in conditions_present
    for key in conditions_present:
        if key == BASELINE_KEY or not baseline_present:
            continue
        paired_base, paired_cond, wins, losses, ties = [], [], 0, 0, 0
        for rid in requirement_ids:
            bs = _item_mean(cells, BASELINE_KEY, rid, reps_present, M.MUTATION_SCORE, True)
            cs = _item_mean(cells, key, rid, reps_present, M.MUTATION_SCORE, True)
            if bs is None or cs is None:
                continue
            paired_base.append(bs)
            paired_cond.append(cs)
            if cs > bs:
                wins += 1
            elif cs < bs:
                losses += 1
            else:
                ties += 1

        n_pairs = len(paired_base)
        if n_pairs == 0:
            comparisons.append({
                "condition": key, "baseline": BASELINE_KEY,
                "metric": M.MUTATION_SCORE, "n_pairs": 0, "insufficient_data": True,
            })
            continue

        base_mean = fmean(paired_base)
        cond_mean = fmean(paired_cond)
        delta = cond_mean - base_mean
        wil = wilcoxon_signed_rank(paired_cond, paired_base)
        comparisons.append({
            "condition": key,
            "condition_label": CONDITIONS[key].label if key in CONDITIONS else key,
            "baseline": BASELINE_KEY,
            "metric": M.MUTATION_SCORE,
            "n_pairs": n_pairs,
            "baseline_mean": round(base_mean, 4),
            "condition_mean": round(cond_mean, 4),
            "mean_delta": round(delta, 4),
            "pct_improvement": round(100.0 * delta / base_mean, 1) if base_mean else None,
            "wins": wins,
            "losses": losses,
            "ties": ties,
            "wilcoxon": wil,
            "p_value": wil["p_value"],
            "significant": wil["p_value"] < 0.05 and n_pairs > 0,
            "cohens_dz": cohens_dz(paired_cond, paired_base),
            "rank_biserial": rank_biserial(paired_cond, paired_base),
        })

    headline = _headline(condition_out, comparisons)

    return {
        "experiment_id": experiment_id,
        "n_items": len(requirement_ids),
        "n_reps": len(reps_present),
        "conditions": condition_out,
        "comparisons": comparisons,
        "headline": headline,
        "fault_types": fault_type_breakdown(db, experiment_id),
    }


def _headline(conditions: list[dict], comparisons: list[dict]) -> dict[str, Any]:
    """Pick the winning condition by mean mutation score and attach its
    baseline comparison — the single sentence the dashboard leads with."""
    scored = [
        (c["metrics"].get(M.MUTATION_SCORE, {}).get("mean", 0.0), c)
        for c in conditions
        if c["metrics"].get(M.MUTATION_SCORE, {}).get("n", 0) > 0
    ]
    if not scored:
        return {"available": False}
    scored.sort(key=lambda t: t[0], reverse=True)
    best_mean, best = scored[0]
    comp = next((c for c in comparisons if c["condition"] == best["key"]), None)
    return {
        "available": True,
        "winner": best["key"],
        "winner_label": best["label"],
        "winner_mutation_score": round(best_mean, 4),
        "comparison": comp,
    }
