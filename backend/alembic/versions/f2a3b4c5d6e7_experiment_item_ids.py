"""Add experiments.item_ids (user-chosen subset for a quick run)

A quick-scope experiment can now run a specific subset of the built-in programs
that the user picked, stored as a JSON list of BenchmarkItem ids. Null falls back
to the default representative subset.

Revision ID: f2a3b4c5d6e7
Revises: e1f2a3b4c5d6
Create Date: 2026-08-25 01:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "f2a3b4c5d6e7"
down_revision: Union[str, Sequence[str], None] = "e1f2a3b4c5d6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("experiments", sa.Column("item_ids", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("experiments", "item_ids")
