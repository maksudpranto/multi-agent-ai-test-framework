"""Sync native enum values that drifted (Postgres only)

The project was developed on SQLite, where enum columns are just text and new
enum members need no DDL. On Postgres, enum columns are a native ENUM type with a
fixed label set, so members added to the models after their creating migration
are missing from the database and cause `invalid input value for enum ...`.

This migration adds the drifted members on Postgres:
  - pipelinestage: 'planning', 'prioritization'
  - runstatus:     'cancelled'

It is a no-op on SQLite. `ALTER TYPE ... ADD VALUE` cannot run inside a normal
transaction, so it runs in an autocommit block.

Revision ID: c9d0e1f2a3b4
Revises: b8c9d0e1f2a3
Create Date: 2026-08-24 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op


revision: str = "c9d0e1f2a3b4"
down_revision: Union[str, Sequence[str], None] = "b8c9d0e1f2a3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# (enum type name -> members that may be missing from an older database)
_MISSING = {
    "pipelinestage": ["planning", "prioritization"],
    "runstatus": ["cancelled"],
}


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return  # SQLite (and others) store enum columns as plain text
    with op.get_context().autocommit_block():
        for enum_name, values in _MISSING.items():
            for value in values:
                op.execute(
                    f"ALTER TYPE {enum_name} ADD VALUE IF NOT EXISTS '{value}'"
                )


def downgrade() -> None:
    # Postgres cannot drop a value from an enum type without recreating it;
    # leaving the extra members in place is harmless.
    pass
