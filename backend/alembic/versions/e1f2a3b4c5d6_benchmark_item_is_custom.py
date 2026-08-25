"""Add benchmark_items.is_custom (user-authored programs)

User-added benchmark programs are stored as ordinary BenchmarkItem rows flagged
is_custom=True so they stay out of the fixed thesis corpus. Existing rows are the
seeded benchmark, so they default to False.

Revision ID: e1f2a3b4c5d6
Revises: d0e1f2a3b4c5
Create Date: 2026-08-25 00:30:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "e1f2a3b4c5d6"
down_revision: Union[str, Sequence[str], None] = "d0e1f2a3b4c5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "benchmark_items",
        sa.Column(
            "is_custom",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )


def downgrade() -> None:
    op.drop_column("benchmark_items", "is_custom")
