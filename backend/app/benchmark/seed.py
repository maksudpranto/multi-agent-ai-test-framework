"""Load the executable micro-benchmark corpus into the database.

``seed_benchmark`` is idempotent: it creates (or refreshes) a hidden
"Benchmark Suite" project + dataset, one ``Requirement`` per program (so the
existing pipeline generates tests from a real NL requirement, exactly as it
would for user-authored work), and the ``BenchmarkItem`` / ``BenchmarkMutant``
rows the fault-detection harness needs. Re-running it keeps the DB in sync with
``corpus.py`` without duplicating rows.
"""
from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.benchmark.corpus import PROGRAMS, fault_type_for
from app.models import (
    BenchmarkItem,
    BenchmarkMutant,
    Dataset,
    Priority,
    Project,
    Requirement,
    RequirementStatus,
    RequirementType,
)

BENCHMARK_NAME = "Benchmark Suite"
BENCHMARK_DESCRIPTION = (
    "Executable micro-benchmark for fault-based (mutation) evaluation. Each "
    "requirement maps to a small program with a reference implementation and "
    "seeded bugs; generated test suites are scored by how many bugs they catch."
)


def _get_or_create_project(db: Session, owner_id: int) -> Project:
    project = db.scalar(
        select(Project).where(
            Project.owner_id == owner_id, Project.name == BENCHMARK_NAME
        )
    )
    if project is None:
        project = Project(
            owner_id=owner_id,
            name=BENCHMARK_NAME,
            description=BENCHMARK_DESCRIPTION,
        )
        db.add(project)
        db.flush()
    return project


def _get_or_create_dataset(db: Session, owner_id: int) -> Dataset:
    dataset = db.scalar(
        select(Dataset).where(
            Dataset.owner_id == owner_id, Dataset.name == BENCHMARK_NAME
        )
    )
    if dataset is None:
        dataset = Dataset(
            owner_id=owner_id,
            name=BENCHMARK_NAME,
            domain="benchmark",
            description=BENCHMARK_DESCRIPTION,
        )
        db.add(dataset)
        db.flush()
    return dataset


def seed_benchmark(db: Session, owner_id: int) -> dict[str, Any]:
    """Idempotently seed the benchmark corpus for one owner. Returns a summary
    of how many items were created vs refreshed."""
    project = _get_or_create_project(db, owner_id)
    dataset = _get_or_create_dataset(db, owner_id)

    created = 0
    refreshed = 0
    item_ids: list[int] = []

    for prog in PROGRAMS:
        item = db.scalar(
            select(BenchmarkItem).where(
                BenchmarkItem.dataset_id == dataset.id,
                BenchmarkItem.slug == prog["slug"],
            )
        )

        # The NL requirement the pipeline generates tests from.
        if item is not None:
            requirement = db.get(Requirement, item.requirement_id)
        else:
            requirement = None
        if requirement is None:
            requirement = Requirement(
                project_id=project.id,
                dataset_id=dataset.id,
                title=prog["title"],
                raw_text=prog["requirement"],
                req_type=RequirementType.feature_description,
                priority=Priority.medium,
                status=RequirementStatus.ready,
            )
            db.add(requirement)
            db.flush()
        else:
            requirement.title = prog["title"]
            requirement.raw_text = prog["requirement"]
            requirement.dataset_id = dataset.id

        if item is None:
            item = BenchmarkItem(
                dataset_id=dataset.id,
                requirement_id=requirement.id,
                slug=prog["slug"],
            )
            db.add(item)
            created += 1
        else:
            refreshed += 1

        item.title = prog["title"]
        item.entrypoint = prog["entrypoint"]
        item.signature = prog["signature"]
        item.params = prog["params"]
        item.canonical_inputs = prog["canonical_inputs"]
        item.reference_code = prog["reference"]
        item.requirement_id = requirement.id
        db.flush()

        # Replace the mutant set so it always mirrors the corpus.
        db.query(BenchmarkMutant).filter(
            BenchmarkMutant.benchmark_item_id == item.id
        ).delete()
        for m in prog["mutants"]:
            db.add(
                BenchmarkMutant(
                    benchmark_item_id=item.id,
                    mutant_key=m["key"],
                    description=m["description"],
                    fault_type=fault_type_for(prog["slug"], m["key"]),
                    code=m["code"],
                )
            )
        db.flush()
        item_ids.append(item.id)

    # Prune benchmark items whose slug is no longer in the corpus (the corpus is
    # authoritative), so re-seeding after the corpus changes never leaves stale
    # programs behind to pollute an experiment. Their mutants cascade-delete.
    current_slugs = {p["slug"] for p in PROGRAMS}
    stale = [
        it
        for it in db.scalars(
            select(BenchmarkItem).where(BenchmarkItem.dataset_id == dataset.id)
        )
        if it.slug not in current_slugs
    ]
    pruned = len(stale)
    for it in stale:
        db.delete(it)
    db.flush()

    db.commit()
    return {
        "dataset_id": dataset.id,
        "project_id": project.id,
        "n_items": len(PROGRAMS),
        "created": created,
        "refreshed": refreshed,
        "pruned": pruned,
        "item_ids": item_ids,
    }
