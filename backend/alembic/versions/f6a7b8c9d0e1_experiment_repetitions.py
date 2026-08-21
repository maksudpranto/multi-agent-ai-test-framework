"""experiment repetitions (repeat runs + reproducibility)

Adds experiments.repetitions and pipeline_runs.repetition so a study can be run
several times: each (item x condition) cell gets one run per repetition, and the
results can report the run-to-run spread (std across repetitions) alongside the
mean — turning LLM non-determinism into a reported reproducibility measure.

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
Create Date: 2026-08-21 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "f6a7b8c9d0e1"
down_revision: Union[str, Sequence[str], None] = "e5f6a7b8c9d0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("experiments", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("repetitions", sa.Integer(), nullable=False, server_default="1")
        )
    with op.batch_alter_table("pipeline_runs", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("repetition", sa.Integer(), nullable=False, server_default="1")
        )


def downgrade() -> None:
    with op.batch_alter_table("pipeline_runs", schema=None) as batch_op:
        batch_op.drop_column("repetition")
    with op.batch_alter_table("experiments", schema=None) as batch_op:
        batch_op.drop_column("repetitions")
