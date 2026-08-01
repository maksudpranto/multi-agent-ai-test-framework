"""modules + generalized requirements (was user_stories)

Introduces the Module layer (§4) and generalizes user_stories into a typed
Requirement (§5): user story / acceptance criteria / BRD / PRD / SRS / use case /
feature description, each with priority, status, and an optional source filename.
PipelineRun.user_story_id becomes requirement_id.

SQLite-safe strategy: create the new tables, copy rows across, drop the old
table and column. Enum columns are plain VARCHAR (no CHECK) so future values
need no DDL.

Revision ID: c3d2b5f8a1e2
Revises: b2c1a4e7d9f0
Create Date: 2026-08-01 00:30:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c3d2b5f8a1e2"
down_revision: Union[str, Sequence[str], None] = "b2c1a4e7d9f0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Module layer.
    op.create_table(
        "modules",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="active"),
        sa.Column("priority", sa.String(length=20), nullable=False, server_default="medium"),
        sa.Column("order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    with op.batch_alter_table("modules", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_modules_project_id"), ["project_id"])

    # 2. Requirements (generalizes user_stories).
    op.create_table(
        "requirements",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("module_id", sa.Integer(), sa.ForeignKey("modules.id"), nullable=True),
        sa.Column("dataset_id", sa.Integer(), sa.ForeignKey("datasets.id"), nullable=True),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("raw_text", sa.Text(), nullable=False),
        sa.Column("req_type", sa.String(length=30), nullable=False, server_default="user_story"),
        sa.Column("priority", sa.String(length=20), nullable=False, server_default="medium"),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="draft"),
        sa.Column("source_filename", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    with op.batch_alter_table("requirements", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_requirements_project_id"), ["project_id"])
        batch_op.create_index(batch_op.f("ix_requirements_module_id"), ["module_id"])
        batch_op.create_index(batch_op.f("ix_requirements_dataset_id"), ["dataset_id"])

    # Carry existing user stories over as user_story-typed requirements.
    op.execute(
        "INSERT INTO requirements "
        "(id, project_id, module_id, dataset_id, title, raw_text, req_type, "
        " priority, status, source_filename, created_at) "
        "SELECT id, project_id, NULL, dataset_id, title, raw_text, 'user_story', "
        "'medium', 'draft', NULL, created_at FROM user_stories"
    )

    # 3. Repoint pipeline_runs.user_story_id -> requirement_id. Drop the old
    # index first so batch's table-recreate doesn't try to rebuild it against a
    # column that no longer exists.
    with op.batch_alter_table("pipeline_runs", schema=None) as batch_op:
        batch_op.add_column(sa.Column("requirement_id", sa.Integer(), nullable=True))
    op.execute("UPDATE pipeline_runs SET requirement_id = user_story_id")
    with op.batch_alter_table("pipeline_runs", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_pipeline_runs_user_story_id"))
        batch_op.drop_column("user_story_id")
        batch_op.create_index(
            batch_op.f("ix_pipeline_runs_requirement_id"), ["requirement_id"]
        )

    op.drop_table("user_stories")


def downgrade() -> None:
    op.create_table(
        "user_stories",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("dataset_id", sa.Integer(), sa.ForeignKey("datasets.id"), nullable=True),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("raw_text", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.execute(
        "INSERT INTO user_stories (id, project_id, dataset_id, title, raw_text, created_at) "
        "SELECT id, project_id, dataset_id, title, raw_text, created_at FROM requirements"
    )
    with op.batch_alter_table("pipeline_runs", schema=None) as batch_op:
        batch_op.add_column(sa.Column("user_story_id", sa.Integer(), nullable=True))
    op.execute("UPDATE pipeline_runs SET user_story_id = requirement_id")
    with op.batch_alter_table("pipeline_runs", schema=None) as batch_op:
        batch_op.drop_column("requirement_id")
    op.drop_table("requirements")
    op.drop_table("modules")
