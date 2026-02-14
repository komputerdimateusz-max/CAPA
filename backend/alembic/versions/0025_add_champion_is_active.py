"""add is_active flag to champions for soft-delete

Revision ID: 0025
Revises: 0024
Create Date: 2026-02-14
"""

from alembic import op
import sqlalchemy as sa


revision = "0025"
down_revision = "0024"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "champions",
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("1")),
    )
    op.execute(sa.text("UPDATE champions SET is_active = 1"))


def downgrade() -> None:
    op.drop_column("champions", "is_active")
