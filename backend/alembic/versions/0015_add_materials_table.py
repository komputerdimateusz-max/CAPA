"""add materials table

Revision ID: 0015_add_materials_table
Revises: 0014_add_component_hc_tables
Create Date: 2026-02-13 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "0015_add_materials_table"
down_revision = "0014_add_component_hc_tables"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "materials",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("part_number", sa.String(length=255), nullable=False),
        sa.Column("description", sa.String(length=500), nullable=True),
        sa.Column("unit", sa.String(length=50), nullable=False),
        sa.Column("price_per_unit", sa.Float(), nullable=False, server_default="0"),
        sa.UniqueConstraint("part_number", name="uq_materials_part_number"),
    )


def downgrade() -> None:
    op.drop_table("materials")
