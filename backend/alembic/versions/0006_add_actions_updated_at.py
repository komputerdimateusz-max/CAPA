from __future__ import annotations

from datetime import datetime

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = "0006_add_actions_updated_at"
down_revision = "0005_add_tags_and_analyses_tables"
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = inspect(op.get_bind())
    columns = {column["name"] for column in inspector.get_columns("actions")}
    if "updated_at" not in columns:
        op.add_column("actions", sa.Column("updated_at", sa.DateTime(), nullable=True))

    now = datetime.utcnow()
    op.execute(
        sa.text(
            "UPDATE actions SET updated_at = COALESCE(updated_at, created_at, :now)"
        ).bindparams(now=now)
    )


def downgrade() -> None:
    inspector = inspect(op.get_bind())
    columns = {column["name"] for column in inspector.get_columns("actions")}
    if "updated_at" in columns:
        op.drop_column("actions", "updated_at")
