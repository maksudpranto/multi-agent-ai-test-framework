"""benchmark_mutants.fault_type for the fault taxonomy

Adds a nullable string column labelling each seeded bug with its fault class
(boundary / wrong_constant / wrong_operator / missing_condition / control_flow).
This lets the evaluation report fault detection broken down by fault class, and
turns the benchmark into a categorised, reusable artifact. The values are
stamped from the corpus' FAULT_TYPES map when the benchmark is (re)seeded.

Revision ID: a7b8c9d0e1f2
Revises: f6a7b8c9d0e1
Create Date: 2026-08-23 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a7b8c9d0e1f2"
down_revision: Union[str, Sequence[str], None] = "f6a7b8c9d0e1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("benchmark_mutants", schema=None) as batch_op:
        batch_op.add_column(sa.Column("fault_type", sa.String(length=40), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("benchmark_mutants", schema=None) as batch_op:
        batch_op.drop_column("fault_type")
