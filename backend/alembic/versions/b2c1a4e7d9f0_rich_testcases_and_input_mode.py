"""rich test cases (test_data/severity/rank) + run input_mode

Adds columns that make a test case executable and prioritisable, and records how
a run's acceptance criteria were obtained (derived from a requirement vs supplied
directly). The new PipelineStage 'prioritization' needs no DDL: enum columns are
plain VARCHAR on SQLite (no CHECK constraint).

Revision ID: b2c1a4e7d9f0
Revises: 94124595f4f1
Create Date: 2026-08-01 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b2c1a4e7d9f0"
down_revision: Union[str, Sequence[str], None] = "94124595f4f1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("test_cases", schema=None) as batch_op:
        batch_op.add_column(sa.Column("test_data", sa.JSON(), nullable=True))
        batch_op.add_column(sa.Column("severity", sa.String(length=50), nullable=True))
        batch_op.add_column(sa.Column("rank", sa.Integer(), nullable=True))
    with op.batch_alter_table("pipeline_runs", schema=None) as batch_op:
        batch_op.add_column(sa.Column("input_mode", sa.String(length=50), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("pipeline_runs", schema=None) as batch_op:
        batch_op.drop_column("input_mode")
    with op.batch_alter_table("test_cases", schema=None) as batch_op:
        batch_op.drop_column("rank")
        batch_op.drop_column("severity")
        batch_op.drop_column("test_data")
