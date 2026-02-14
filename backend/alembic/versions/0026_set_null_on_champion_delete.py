"""set champion foreign keys to on delete set null

Revision ID: 0026
Revises: 0025
Create Date: 2026-02-14
"""

from alembic import op
import sqlalchemy as sa


revision = "0026"
down_revision = "0025"
branch_labels = None
depends_on = None


def _rebuild_actions(*, ondelete: str | None) -> None:
    old_table = "actions_old_fk"
    op.rename_table("actions", old_table)
    op.create_table(
        "actions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id"), nullable=True),
        sa.Column("champion_id", sa.Integer(), sa.ForeignKey("champions.id", ondelete=ondelete), nullable=True),
        sa.Column("owner", sa.String(length=255), nullable=True),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("due_date", sa.Date(), nullable=True),
        sa.Column("closed_at", sa.DateTime(), nullable=True),
        sa.Column("priority", sa.String(length=50), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.Column("process_type", sa.String(length=32), nullable=True),
    )
    op.execute(
        sa.text(
            """
            INSERT INTO actions (
                id, title, description, project_id, champion_id, owner,
                status, created_at, due_date, closed_at, priority, updated_at, process_type
            )
            SELECT
                id, title, description, project_id, champion_id, owner,
                status, created_at, due_date, closed_at, priority, updated_at, process_type
            FROM actions_old_fk
            """
        )
    )
    op.drop_table(old_table)


def _rebuild_projects(*, ondelete: str | None) -> None:
    old_table = "projects_old_fk"
    op.rename_table("projects", old_table)
    op.create_table(
        "projects",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("due_date", sa.Date(), nullable=True),
        sa.Column("status", sa.String(length=50), nullable=True),
        sa.Column("max_volume", sa.Integer(), nullable=True),
        sa.Column("flex_percent", sa.Float(), nullable=True),
        sa.Column(
            "process_engineer_id",
            sa.Integer(),
            sa.ForeignKey("champions.id", ondelete=ondelete),
            nullable=True,
        ),
    )
    op.execute(
        sa.text(
            """
            INSERT INTO projects (id, name, due_date, status, max_volume, flex_percent, process_engineer_id)
            SELECT id, name, due_date, status, max_volume, flex_percent, process_engineer_id
            FROM projects_old_fk
            """
        )
    )
    op.drop_table(old_table)


def _rebuild_users(*, ondelete: str | None) -> None:
    old_table = "users_old_fk"
    op.rename_table("users", old_table)
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("username", sa.String(length=150), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("role", sa.String(length=50), nullable=False),
        sa.Column("champion_id", sa.Integer(), sa.ForeignKey("champions.id", ondelete=ondelete), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("1")),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("username"),
        sa.UniqueConstraint("email"),
    )
    op.execute(
        sa.text(
            """
            INSERT INTO users (id, username, email, password_hash, role, champion_id, is_active, created_at)
            SELECT id, username, email, password_hash, role, champion_id, is_active, created_at
            FROM users_old_fk
            """
        )
    )
    op.drop_table(old_table)


def upgrade() -> None:
    op.execute(sa.text("PRAGMA foreign_keys=OFF"))
    try:
        _rebuild_projects(ondelete="SET NULL")
        _rebuild_actions(ondelete="SET NULL")
        _rebuild_users(ondelete="SET NULL")
    finally:
        op.execute(sa.text("PRAGMA foreign_keys=ON"))


def downgrade() -> None:
    op.execute(sa.text("PRAGMA foreign_keys=OFF"))
    try:
        _rebuild_projects(ondelete=None)
        _rebuild_actions(ondelete=None)
        _rebuild_users(ondelete=None)
    finally:
        op.execute(sa.text("PRAGMA foreign_keys=ON"))
