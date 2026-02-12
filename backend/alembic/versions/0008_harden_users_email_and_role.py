from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = "0008_harden_users_email_and_role"
down_revision = "0007_extend_projects_fields"
branch_labels = None
depends_on = None


def _users_columns() -> set[str]:
    bind = op.get_bind()
    inspector = inspect(bind)
    if not inspector.has_table("users"):
        return set()
    return {column["name"] for column in inspector.get_columns("users")}


def _users_indexes() -> set[str]:
    bind = op.get_bind()
    inspector = inspect(bind)
    if not inspector.has_table("users"):
        return set()
    return {index["name"] for index in inspector.get_indexes("users")}


def upgrade() -> None:
    columns = _users_columns()
    if not columns:
        return

    bind = op.get_bind()

    if "role" not in columns:
        with op.batch_alter_table("users") as batch:
            batch.add_column(sa.Column("role", sa.String(length=50), nullable=True))

    if "email" not in columns:
        with op.batch_alter_table("users") as batch:
            batch.add_column(sa.Column("email", sa.String(length=255), nullable=True))

    bind.execute(sa.text("UPDATE users SET role = 'viewer' WHERE role IS NULL OR trim(role) = ''"))
    bind.execute(
        sa.text(
            "UPDATE users SET email = lower(username) || '@local.invalid' "
            "WHERE email IS NULL OR trim(email) = ''"
        )
    )

    with op.batch_alter_table("users") as batch:
        batch.alter_column("role", existing_type=sa.String(length=50), nullable=False)
        batch.alter_column("email", existing_type=sa.String(length=255), nullable=False)

    indexes = _users_indexes()
    if "ix_users_email" not in indexes:
        op.create_index("ix_users_email", "users", ["email"], unique=True)


def downgrade() -> None:
    indexes = _users_indexes()
    if "ix_users_email" in indexes:
        op.drop_index("ix_users_email", table_name="users")

    columns = _users_columns()
    if not columns:
        return

    if "email" in columns:
        with op.batch_alter_table("users") as batch:
            batch.alter_column("email", existing_type=sa.String(length=255), nullable=True)
