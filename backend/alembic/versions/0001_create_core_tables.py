from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = "0001_create_core_tables"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = inspect(bind)
    existing_tables = set(insp.get_table_names())

    if "champions" not in existing_tables:
        op.create_table(
            "champions",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("name", sa.String(length=255), nullable=False),
        )
    if "projects" not in existing_tables:
        op.create_table(
            "projects",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("name", sa.String(length=255), nullable=False),
            sa.Column("due_date", sa.Date(), nullable=True),
            sa.Column("status", sa.String(length=50), nullable=True),
        )
    if "actions" not in existing_tables:
        op.create_table(
            "actions",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("title", sa.String(length=255), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id"), nullable=True),
            sa.Column("champion_id", sa.Integer(), sa.ForeignKey("champions.id"), nullable=True),
            sa.Column("owner", sa.String(length=255), nullable=True),
            sa.Column("status", sa.String(length=50), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("due_date", sa.Date(), nullable=True),
            sa.Column("closed_at", sa.DateTime(), nullable=True),
            sa.Column("tags", sa.JSON(), nullable=False),
            sa.Column("priority", sa.String(length=50), nullable=True),
        )
    if "subtasks" not in existing_tables:
        op.create_table(
            "subtasks",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("action_id", sa.Integer(), sa.ForeignKey("actions.id"), nullable=False),
            sa.Column("title", sa.String(length=255), nullable=False),
            sa.Column("status", sa.String(length=50), nullable=False),
            sa.Column("due_date", sa.Date(), nullable=True),
            sa.Column("closed_at", sa.DateTime(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
        )


def downgrade() -> None:
    op.drop_table("subtasks")
    op.drop_table("actions")
    op.drop_table("projects")
    op.drop_table("champions")
