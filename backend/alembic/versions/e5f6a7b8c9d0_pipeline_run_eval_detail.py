"""pipeline_runs.eval_detail for the fault-detection drill-down

Adds a nullable JSON column holding the per-run fault-detection detail (harvested
inputs + per-mutant killed/killed-by-input), so the results drill-down can show
the concrete bug, the input that exposed it, and the caught/missed verdict.

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-08-21 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "e5f6a7b8c9d0"
down_revision: Union[str, Sequence[str], None] = "d4e5f6a7b8c9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("pipeline_runs", schema=None) as batch_op:
        batch_op.add_column(sa.Column("eval_detail", sa.JSON(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("pipeline_runs", schema=None) as batch_op:
        batch_op.drop_column("eval_detail")
