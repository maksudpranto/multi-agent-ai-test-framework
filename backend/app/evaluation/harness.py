"""Fault-detection harness: reference-as-oracle differential testing.

This is the empirical heart of the thesis. A generated test suite is natural
language, so its ``expected_result`` is a poor oracle. Instead we:

  1. **Materialize** the concrete input arguments the suite implies
     (``materialize_inputs`` — one narrow, temperature-0 LLM call, with a
     deterministic ``canonical_inputs`` fallback), then
  2. run the **reference** implementation on those inputs — it is the oracle —
     and run every **mutant** (a reference with one seeded bug) on the same
     inputs, and
  3. count a mutant as *killed* if its behaviour diverges from the reference on
     any input (different return value, different exception class, or a timeout).

``mutation_score = killed / total``. The identical materializer runs for every
experiment condition, so the comparison between single-LLM and multi-agent is
fair: the only thing that varies is the suite each produced, hence the inputs it
harvests, hence how many bugs it catches.

Execution never happens in this process — see ``_runner.py`` (isolated
subprocess, resource-limited, timed). This module only orchestrates and scores.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any

_RUNNER = str(Path(__file__).resolve().parent / "_runner.py")

# One call is bounded so a pathological input cannot wedge a run.
PER_INPUT_TIMEOUT = 2.0
# Hard cap on inputs actually executed per suite, to bound run time regardless
# of how many the materializer returns.
MAX_INPUTS = 16


# ---------------------------------------------------------------------------
# Sandboxed execution
# ---------------------------------------------------------------------------


def _exec(code: str, entrypoint: str, inputs: list[list]) -> list[dict[str, Any]]:
    """Run ``entrypoint(*args)`` for each input in an isolated subprocess.

    Returns one outcome dict per input: ``{"status": "ok"|"error"|"timeout",
    "key": str}``. Never raises for benchmark-code failures — a raised exception
    or a timeout is itself a recorded outcome, which is what makes divergence
    detectable."""
    if not inputs:
        return []

    job = json.dumps(
        {
            "code": code,
            "entrypoint": entrypoint,
            "inputs": inputs,
            "per_input_timeout": PER_INPUT_TIMEOUT,
        }
    )
    wall_timeout = PER_INPUT_TIMEOUT * len(inputs) + 5.0
    env = {"PATH": "/usr/bin:/bin", "PYTHONHASHSEED": "0"}

    with tempfile.TemporaryDirectory(prefix="benchsbx_") as tmp:
        proc = subprocess.Popen(
            [sys.executable, "-I", _RUNNER],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=tmp,
            env=env,
            text=True,
            start_new_session=True,  # own process group, so we can kill the tree
        )
        try:
            out, _err = proc.communicate(input=job, timeout=wall_timeout)
        except subprocess.TimeoutExpired:
            _kill_group(proc)
            proc.communicate()
            # Whole batch wedged: treat every input as a timeout kill.
            return [{"status": "timeout", "key": ""} for _ in inputs]

    try:
        payload = json.loads(out)
    except (json.JSONDecodeError, ValueError):
        return [{"status": "error", "key": "HarnessError"} for _ in inputs]

    if payload.get("load_error"):
        # Code failed to load at all: mark every input with a load error so it
        # compares equal across variants (a load bug is not a "kill").
        return [{"status": "error", "key": "LoadError"} for _ in inputs]

    results = payload.get("results", [])
    # Defensive: pad/truncate to len(inputs) so callers can zip safely.
    if len(results) < len(inputs):
        results = results + [
            {"status": "error", "key": "MissingResult"}
            for _ in range(len(inputs) - len(results))
        ]
    return results[: len(inputs)]


def _kill_group(proc: subprocess.Popen) -> None:
    try:
        os.killpg(os.getpgid(proc.pid), 9)
    except (ProcessLookupError, PermissionError):
        try:
            proc.kill()
        except ProcessLookupError:
            pass


def _diverges(ref: dict, mut: dict) -> bool:
    """True if the mutant's outcome differs from the reference's on one input:
    a different status (ok vs error vs timeout), or the same status with a
    different value/exception key."""
    if ref["status"] != mut["status"]:
        return True
    return ref["key"] != mut["key"]


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------


@dataclass
class FaultDetectionResult:
    """Outcome of scoring one suite against one benchmark item."""

    mutation_score: float  # killed / total over usable inputs
    suite_valid: bool  # at least one input the reference handled normally
    killed: int
    total: int
    n_inputs: int  # inputs actually executed
    n_usable_inputs: int  # inputs where the reference returned normally (oracle)
    materialized: bool  # inputs came from the LLM (True) or the fallback (False)
    inputs: list[list] = field(default_factory=list)
    per_mutant: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def score_suite(
    *,
    reference_code: str,
    mutants: list[dict],
    entrypoint: str,
    inputs: list[list],
    materialized: bool = True,
) -> FaultDetectionResult:
    """Score a suite's harvested ``inputs`` against a benchmark item.

    ``mutants`` is a list of ``{"key", "code"}``. A mutant is killed if it
    diverges from the reference on any *usable* input — one the reference itself
    handled normally (returned a value). If the reference errors on every input,
    the oracle is untrustworthy: ``suite_valid`` is False and the cell is meant
    to be dropped from the aggregated statistics."""
    inputs = [list(x) for x in inputs][:MAX_INPUTS]
    total = len(mutants)

    if not inputs:
        return FaultDetectionResult(
            mutation_score=0.0, suite_valid=False, killed=0, total=total,
            n_inputs=0, n_usable_inputs=0, materialized=materialized, inputs=[],
            per_mutant=[
                {"key": m["key"], "fault_type": m.get("fault_type"), "killed": False}
                for m in mutants
            ],
        )

    ref_outcomes = _exec(reference_code, entrypoint, inputs)
    usable = [i for i, o in enumerate(ref_outcomes) if o["status"] == "ok"]
    suite_valid = len(usable) > 0

    per_mutant: list[dict] = []
    killed = 0
    for m in mutants:
        mut_outcomes = _exec(m["code"], entrypoint, inputs)
        kill_idx = next(
            (i for i in usable if _diverges(ref_outcomes[i], mut_outcomes[i])),
            None,
        )
        was_killed = kill_idx is not None
        killed += 1 if was_killed else 0
        per_mutant.append(
            {
                "key": m["key"],
                "fault_type": m.get("fault_type"),
                "killed": was_killed,
                "killed_by_input": inputs[kill_idx] if was_killed else None,
            }
        )

    score = round(killed / total, 4) if (total and suite_valid) else 0.0
    return FaultDetectionResult(
        mutation_score=score,
        suite_valid=suite_valid,
        killed=killed,
        total=total,
        n_inputs=len(inputs),
        n_usable_inputs=len(usable),
        materialized=materialized,
        inputs=inputs,
        per_mutant=per_mutant,
    )


# ---------------------------------------------------------------------------
# Input materialization (suite -> concrete argument lists)
# ---------------------------------------------------------------------------

_MATERIALIZE_SYS = (
    "You are a test-input materializer. You convert a natural-language test "
    "suite into concrete argument lists for a Python function. You do not judge "
    "correctness; you only extract the distinct inputs the suite intends to "
    "exercise. Return ONLY JSON."
)


def _materialize_prompt(
    *, signature: str, params: list[dict] | None, suite_cases: list[dict],
    canonical_inputs: list[list],
) -> str:
    params = params or []
    param_lines = "\n".join(
        f"  - {p.get('name')}: {p.get('type')} — {p.get('note', '')}" for p in params
    )
    cases_json = json.dumps(suite_cases, ensure_ascii=False, indent=2)
    example = json.dumps(canonical_inputs)
    arity = len(params)
    return (
        f"Function under test:\n  {signature}\n\n"
        f"Positional parameters (in order):\n{param_lines}\n\n"
        "Here is a natural-language test suite written for this function. Each "
        "case describes a scenario (title, steps, expected_result, test_data):\n"
        f"{cases_json}\n\n"
        "Task: translate THIS suite into concrete argument tuples — one tuple per "
        "distinct scenario the suite actually describes. Stay faithful to the "
        "suite: derive each input from the scenarios, values and edge cases the "
        "test cases mention. Do NOT invent extra categories of edge case that the "
        "suite does not test — a thorough suite should yield more inputs, a thin "
        "one fewer. This keeps the evaluation fair: the suite's own coverage is "
        "what determines the inputs.\n\n"
        "Return ONLY a JSON array of arrays. Each inner array is the positional "
        f"arguments for one call, with exactly {arity} element(s) in parameter "
        "order, using JSON literals (numbers, strings, booleans).\n"
        f"Example shape (do not just copy it): {example}\n"
    )


def _coerce_inputs(raw: Any, arity: int) -> list[list]:
    """Accept only a list of fixed-arity argument lists. Anything else -> []."""
    if not isinstance(raw, list):
        return []
    out: list[list] = []
    for item in raw:
        if isinstance(item, list) and len(item) == arity:
            out.append(item)
        elif arity == 1 and not isinstance(item, (list, dict)):
            # Tolerate a flat list of scalars for single-argument functions.
            out.append([item])
    # De-duplicate while preserving order.
    seen: set[str] = set()
    deduped: list[list] = []
    for x in out:
        key = json.dumps(x, sort_keys=True)
        if key not in seen:
            seen.add(key)
            deduped.append(x)
    return deduped


def materialize_inputs(
    llm_service,
    *,
    signature: str,
    params: list[dict] | None,
    canonical_inputs: list[list],
    suite_cases: list[dict],
    model: str,
) -> tuple[list[list], bool]:
    """Harvest concrete argument lists from a NL suite.

    One temperature-0 LLM call with a single retry; on unparseable/empty output
    it falls back to ``canonical_inputs`` so the harness always has valid inputs.
    Returns ``(inputs, materialized)`` where ``materialized`` is True iff the LLM
    produced the inputs.

    The inputs are harvested *only* from the suite — the canonical inputs are the
    fallback, never merged into a real suite's set. That is deliberate and load-
    bearing: the whole comparison rests on a richer suite (more boundary/negative
    cases) harvesting inputs that kill more mutants than a thin one. Folding the
    canonical inputs into every suite would erase that signal and make every
    condition score identically."""
    arity = len(params or [])
    prompt = _materialize_prompt(
        signature=signature, params=params, suite_cases=suite_cases,
        canonical_inputs=canonical_inputs,
    )

    for _attempt in range(2):
        try:
            parsed, _resp = llm_service.complete_json(
                prompt=prompt, model=model, system=_MATERIALIZE_SYS,
                temperature=0.0, max_tokens=1024,
            )
        except Exception:  # noqa: BLE001 - bad JSON / provider error -> retry then fall back
            continue
        harvested = _coerce_inputs(parsed, arity)
        if harvested:
            return (harvested[:MAX_INPUTS], True)

    return ([list(x) for x in canonical_inputs][:MAX_INPUTS], False)
