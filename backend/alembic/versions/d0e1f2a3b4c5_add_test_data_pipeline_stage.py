"""Add the 'test_data' pipeline stage (Postgres enum, on-demand Test Data agent)

The Test Data agent introduces a new PipelineStage member, `test_data`. On
SQLite enum columns are plain text so no DDL is needed; on Postgres the native
`pipelinestage` ENUM must gain the label or `AgentExecution` inserts fail with
`invalid input value for enum pipelinestage: "test_data"`.

No-op on SQLite. `ALTER TYPE ... ADD VALUE` can't run inside a transaction, so
it runs in an autocommit block.

Revision ID: d0e1f2a3b4c5
Revises: c9d0e1f2a3b4
Create Date: 2026-08-25 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op


revision: str = "d0e1f2a3b4c5"
down_revision: Union[str, Sequence[str], None] = "c9d0e1f2a3b4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return  # SQLite (and others) store enum columns as plain text
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE pipelinestage ADD VALUE IF NOT EXISTS 'test_data'")


def downgrade() -> None:
    # Postgres cannot drop a value from an enum type without recreating it;
    # leaving the extra member in place is harmless.
    pass
