"""Phase 1 verification for the fault-detection harness.

The gate the whole thesis rests on: seeded bugs are *killed* by good inputs and
*survive* weak ones, the sandbox records divergence correctly (wrong value,
wrong type, raised exception, timeout), the suite-validity gate fires when the
reference cannot run, and the materializer falls back to canonical inputs on
unusable LLM output. Runs entirely on the deterministic corpus + mock provider
— no API key, no network.
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.benchmark.corpus import PROGRAMS
from app.benchmark.seed import seed_benchmark
from app.database import Base
from app.evaluation.harness import materialize_inputs, score_suite
from app.llm import LLMService
from app.llm.mock_provider import MockProvider
from app.models import BenchmarkItem, BenchmarkMutant, User


def _prog(slug: str) -> dict:
    return next(p for p in PROGRAMS if p["slug"] == slug)


def _mutants(prog: dict) -> list[dict]:
    return [{"key": m["key"], "code": m["code"]} for m in prog["mutants"]]


# --- The core gate: good inputs kill, weak inputs survive --------------------


def test_good_inputs_kill_every_mutant_across_corpus():
    """Each program's canonical (good) inputs should kill all three seeded bugs."""
    for prog in PROGRAMS:
        result = score_suite(
            reference_code=prog["reference"],
            mutants=_mutants(prog),
            entrypoint=prog["entrypoint"],
            inputs=prog["canonical_inputs"],
        )
        assert result.suite_valid, prog["slug"]
        assert result.killed == result.total == 3, (
            prog["slug"],
            [m for m in result.per_mutant if not m["killed"]],
        )
        assert result.mutation_score == 1.0, prog["slug"]


def test_weak_inputs_let_boundary_mutant_survive():
    """A thin suite that omits the boundary case misses the off-by-one mutant.

    grade_calculator m1 moves the 'A' cut-off from 90 to 89; only an input at
    the 89/90 boundary reveals it. A weak suite of interior points does not."""
    prog = _prog("grade_calculator")
    weak_inputs = [[95], [50]]  # clearly-A and clearly-F, no boundary
    result = score_suite(
        reference_code=prog["reference"],
        mutants=_mutants(prog),
        entrypoint=prog["entrypoint"],
        inputs=weak_inputs,
    )
    survivors = {m["key"] for m in result.per_mutant if not m["killed"]}
    assert "m1" in survivors  # boundary bug survives the weak suite
    assert result.mutation_score < 1.0
    # And adding the boundary input flips it to killed.
    strong = score_suite(
        reference_code=prog["reference"],
        mutants=_mutants(prog),
        entrypoint=prog["entrypoint"],
        inputs=weak_inputs + [[89]],
    )
    assert all(m["killed"] for m in strong.per_mutant if m["key"] == "m1")


# --- Sandbox behaviours ------------------------------------------------------


def test_type_only_divergence_is_a_kill():
    """fizzbuzz m3 returns an int 7 where the reference returns the str '7'."""
    prog = _prog("fizzbuzz")
    result = score_suite(
        reference_code=prog["reference"],
        mutants=[{"key": "m3", "code": _prog("fizzbuzz")["mutants"][2]["code"]}],
        entrypoint="fizzbuzz",
        inputs=[[7]],
    )
    assert result.killed == 1


def test_raised_exception_diverges_from_returned_value():
    ref = "def f(x):\n    return x + 1\n"
    mutant = "def f(x):\n    raise ValueError('boom')\n"
    result = score_suite(
        reference_code=ref,
        mutants=[{"key": "exc", "code": mutant}],
        entrypoint="f",
        inputs=[[1]],
    )
    assert result.per_mutant[0]["killed"]


def test_timeout_is_killed_and_reference_stays_usable():
    """An infinite-loop mutant times out (a kill); a per-input timer keeps one
    slow input from wedging the whole batch."""
    ref = "def f(x):\n    return x\n"
    mutant = "def f(x):\n    while True:\n        pass\n"
    result = score_suite(
        reference_code=ref,
        mutants=[{"key": "loop", "code": mutant}],
        entrypoint="f",
        inputs=[[1]],
    )
    assert result.suite_valid
    assert result.per_mutant[0]["killed"]


def test_identical_code_kills_nothing():
    prog = _prog("leap_year")
    result = score_suite(
        reference_code=prog["reference"],
        mutants=[{"key": "clone", "code": prog["reference"]}],
        entrypoint=prog["entrypoint"],
        inputs=prog["canonical_inputs"],
    )
    assert result.killed == 0
    assert result.mutation_score == 0.0


def test_suite_invalid_when_reference_never_runs():
    """If the reference errors on every input (bad arity), the oracle is
    untrustworthy: suite_valid is False and the score is zeroed."""
    ref = "def f(x):\n    return x\n"
    mutant = "def f(x):\n    return x + 1\n"
    result = score_suite(
        reference_code=ref,
        mutants=[{"key": "m", "code": mutant}],
        entrypoint="f",
        inputs=[[1, 2, 3], [4, 5, 6]],  # too many args -> reference raises
    )
    assert not result.suite_valid
    assert result.n_usable_inputs == 0
    assert result.mutation_score == 0.0


def test_empty_suite_scores_zero_and_is_invalid():
    prog = _prog("bmi_calculator")
    result = score_suite(
        reference_code=prog["reference"],
        mutants=_mutants(prog),
        entrypoint=prog["entrypoint"],
        inputs=[],
    )
    assert not result.suite_valid
    assert result.mutation_score == 0.0
    assert result.total == 3


# --- Materializer ------------------------------------------------------------


def test_materializer_falls_back_to_canonical_on_bad_output():
    """The mock provider returns '{}' for the materializer prompt (no matching
    branch), which is unusable -> fall back to canonical inputs."""
    prog = _prog("bmi_calculator")
    llm = LLMService(MockProvider(response="{}"))
    inputs, materialized = materialize_inputs(
        llm,
        signature=prog["signature"],
        params=prog["params"],
        canonical_inputs=prog["canonical_inputs"],
        suite_cases=[{"title": "some case"}],
        model="mock",
    )
    assert materialized is False
    assert inputs == prog["canonical_inputs"]


def test_materializer_accepts_wellformed_llm_inputs():
    prog = _prog("fizzbuzz")
    llm = LLMService(MockProvider(response="[[3], [5], [15], [7]]"))
    inputs, materialized = materialize_inputs(
        llm,
        signature=prog["signature"],
        params=prog["params"],
        canonical_inputs=prog["canonical_inputs"],
        suite_cases=[{"title": "x"}],
        model="mock",
    )
    assert materialized is True
    assert inputs == [[3], [5], [15], [7]]


def test_materializer_rejects_wrong_arity():
    """Two-arg tuples for a one-arg function are dropped; nothing usable
    remains, so it falls back."""
    prog = _prog("fizzbuzz")
    llm = LLMService(MockProvider(response="[[1, 2], [3, 4]]"))
    inputs, materialized = materialize_inputs(
        llm,
        signature=prog["signature"],
        params=prog["params"],
        canonical_inputs=prog["canonical_inputs"],
        suite_cases=[{"title": "x"}],
        model="mock",
    )
    assert materialized is False
    assert inputs == prog["canonical_inputs"]


# --- Seeding -----------------------------------------------------------------


def _mem_db():
    engine = create_engine(
        "sqlite:///:memory:", connect_args={"check_same_thread": False}
    )
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def test_seed_benchmark_is_idempotent_and_complete():
    db = _mem_db()
    try:
        user = User(email="b@e.com", hashed_password="x")
        db.add(user)
        db.commit()

        first = seed_benchmark(db, user.id)
        assert first["created"] == len(PROGRAMS)
        assert first["refreshed"] == 0

        second = seed_benchmark(db, user.id)
        assert second["created"] == 0
        assert second["refreshed"] == len(PROGRAMS)

        assert db.query(BenchmarkItem).count() == len(PROGRAMS)
        assert db.query(BenchmarkMutant).count() == len(PROGRAMS) * 3
        # Every item is bound to a real requirement the pipeline can consume.
        for item in db.query(BenchmarkItem).all():
            assert item.requirement is not None
            assert item.requirement.raw_text
            assert item.reference_code
    finally:
        db.close()
