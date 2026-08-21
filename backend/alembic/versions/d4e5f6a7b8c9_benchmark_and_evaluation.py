"""benchmark corpus + evaluation experiment fields

Adds the executable-benchmark tables (benchmark_items, benchmark_mutants) that
back the fault-based evaluation, plus two evaluation fields on existing tables:
  - pipeline_runs.experiment_condition — which arm produced a run (single_llm /
    full_pipeline / ablation_no_debate), the key the aggregation groups by.
  - experiments.conditions — the JSON list of arms an experiment runs.

SQLite-safe: new tables are created outright; the two columns are added with
batch_alter_table so SQLite's limited ALTER is handled by table-recreate.

Revision ID: d4e5f6a7b8c9
Revises: c3d2b5f8a1e2
Create Date: 2026-08-21 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d4e5f6a7b8c9"
down_revision: Union[str, Sequence[str], None] = "c3d2b5f8a1e2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Benchmark items: one small program each (requirement + reference oracle).
    op.create_table(
        "benchmark_items",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("dataset_id", sa.Integer(), sa.ForeignKey("datasets.id"), nullable=False),
        sa.Column("requirement_id", sa.Integer(), sa.ForeignKey("requirements.id"), nullable=False),
        sa.Column("slug", sa.String(length=100), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("entrypoint", sa.String(length=100), nullable=False),
        sa.Column("signature", sa.String(length=255), nullable=True),
        sa.Column("params", sa.JSON(), nullable=True),
        sa.Column("canonical_inputs", sa.JSON(), nullable=True),
        sa.Column("reference_code", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    with op.batch_alter_table("benchmark_items", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_benchmark_items_dataset_id"), ["dataset_id"])
        batch_op.create_index(batch_op.f("ix_benchmark_items_requirement_id"), ["requirement_id"])
        batch_op.create_index(batch_op.f("ix_benchmark_items_slug"), ["slug"])

    # 2. Benchmark mutants: reference with one seeded bug.
    op.create_table(
        "benchmark_mutants",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("benchmark_item_id", sa.Integer(), sa.ForeignKey("benchmark_items.id"), nullable=False),
        sa.Column("mutant_key", sa.String(length=50), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("code", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    with op.batch_alter_table("benchmark_mutants", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_benchmark_mutants_benchmark_item_id"), ["benchmark_item_id"]
        )

    # 3. Evaluation fields on existing tables.
    with op.batch_alter_table("pipeline_runs", schema=None) as batch_op:
        batch_op.add_column(sa.Column("experiment_condition", sa.String(length=50), nullable=True))
        batch_op.create_index(
            batch_op.f("ix_pipeline_runs_experiment_condition"), ["experiment_condition"]
        )
    with op.batch_alter_table("experiments", schema=None) as batch_op:
        batch_op.add_column(sa.Column("conditions", sa.JSON(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("experiments", schema=None) as batch_op:
        batch_op.drop_column("conditions")
    with op.batch_alter_table("pipeline_runs", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_pipeline_runs_experiment_condition"))
        batch_op.drop_column("experiment_condition")
    op.drop_table("benchmark_mutants")
    op.drop_table("benchmark_items")
