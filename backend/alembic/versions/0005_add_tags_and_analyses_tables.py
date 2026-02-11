from __future__ import annotations

import json

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = "0005_add_tags_and_analyses_tables"
down_revision = "0004_add_users_email"
branch_labels = None
depends_on = None


def _table_columns(table_name: str) -> set[str]:
    inspector = inspect(op.get_bind())
    if not inspector.has_table(table_name):
        return set()
    return {column["name"] for column in inspector.get_columns(table_name)}


def upgrade() -> None:
    op.create_table(
        "analyses",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("type", sa.String(length=20), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("champion", sa.String(length=255), nullable=True),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("created_at", sa.Date(), nullable=False),
        sa.Column("closed_at", sa.Date(), nullable=True),
    )
    op.create_table(
        "tags",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=64), nullable=False, unique=True),
        sa.Column("color", sa.String(length=32), nullable=True),
    )
    op.create_table(
        "action_tags",
        sa.Column("action_id", sa.Integer(), sa.ForeignKey("actions.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("tag_id", sa.Integer(), sa.ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True),
    )
    op.create_table(
        "analysis_tags",
        sa.Column("analysis_id", sa.String(length=64), sa.ForeignKey("analyses.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("tag_id", sa.Integer(), sa.ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True),
    )

    if "tags" in _table_columns("actions"):
        bind = op.get_bind()
        rows = bind.execute(sa.text("SELECT id, tags FROM actions")).fetchall()
        tag_ids: dict[str, int] = {}
        for row in rows:
            action_id = row[0]
            raw = row[1]
            values: list[str] = []
            if isinstance(raw, list):
                values = [str(item).strip() for item in raw if str(item).strip()]
            elif isinstance(raw, str) and raw.strip():
                try:
                    parsed = json.loads(raw)
                    if isinstance(parsed, list):
                        values = [str(item).strip() for item in parsed if str(item).strip()]
                except json.JSONDecodeError:
                    pass
            for value in values:
                key = value.lower()
                tag_id = tag_ids.get(key)
                if tag_id is None:
                    bind.execute(sa.text("INSERT INTO tags (name) VALUES (:name)"), {"name": value})
                    tag_id = int(bind.execute(sa.text("SELECT id FROM tags WHERE lower(name)=:name"), {"name": key}).scalar_one())
                    tag_ids[key] = tag_id
                bind.execute(
                    sa.text(
                        "INSERT INTO action_tags (action_id, tag_id) VALUES (:action_id, :tag_id) "
                        "ON CONFLICT DO NOTHING"
                    ),
                    {"action_id": action_id, "tag_id": tag_id},
                )

        with op.batch_alter_table("actions") as batch:
            batch.drop_column("tags")


def downgrade() -> None:
    with op.batch_alter_table("actions") as batch:
        batch.add_column(sa.Column("tags", sa.JSON(), nullable=False, server_default="[]"))

    op.drop_table("analysis_tags")
    op.drop_table("action_tags")
    op.drop_table("tags")
    op.drop_table("analyses")
