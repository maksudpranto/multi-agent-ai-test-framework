"""experiments.scope for quick vs full runs

Adds a string column selecting how many benchmark programs a run covers:
"full" (all programs) or "quick" (a small representative subset). This lets a
run be bounded for cheap/fast iteration now that the benchmark has grown, while
the thesis result still uses a full run.

Revision ID: b8c9d0e1f2a3
Revises: a7b8c9d0e1f2
Create Date: 2026-08-23 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b8c9d0e1f2a3"
down_revision: Union[str, Sequence[str], None] = "a7b8c9d0e1f2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("experiments", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("scope", sa.String(length=20), nullable=False, server_default="full")
        )


def downgrade() -> None:
    with op.batch_alter_table("experiments", schema=None) as batch_op:
        batch_op.drop_column("scope")
