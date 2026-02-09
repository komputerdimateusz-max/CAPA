from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = "0004_add_users_email"
down_revision = "0003_update_champion_fields"
branch_labels = None
depends_on = None


EMAIL_COLUMN = sa.Column("email", sa.String(length=255), nullable=True)


def _users_columns() -> set[str]:
    bind = op.get_bind()
    inspector = inspect(bind)
    if not inspector.has_table("users"):
        return set()
    return {column["name"] for column in inspector.get_columns("users")}


def upgrade() -> None:
    columns = _users_columns()
    if not columns or "email" in columns:
        return

    with op.batch_alter_table("users") as batch:
        batch.add_column(EMAIL_COLUMN)


def downgrade() -> None:
    columns = _users_columns()
    if not columns or "email" not in columns:
        return

    with op.batch_alter_table("users") as batch:
        batch.drop_column("email")
