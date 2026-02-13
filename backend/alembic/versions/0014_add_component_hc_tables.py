"""add component hc tables

Revision ID: 0014_add_component_hc_tables
Revises: 0013_add_labour_costs_table
Create Date: 2026-02-13 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "0014_add_component_hc_tables"
down_revision = "0013_add_labour_costs_table"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "moulding_tool_hc",
        sa.Column("tool_id", sa.Integer(), sa.ForeignKey("moulding_tools.id", ondelete="CASCADE"), nullable=False),
        sa.Column("worker_type", sa.String(length=100), nullable=False),
        sa.Column("hc", sa.Float(), nullable=False, server_default="0"),
        sa.PrimaryKeyConstraint("tool_id", "worker_type", name="pk_moulding_tool_hc"),
    )

    op.create_table(
        "metalization_mask_hc",
        sa.Column("mask_id", sa.Integer(), sa.ForeignKey("metalization_masks.id", ondelete="CASCADE"), nullable=False),
        sa.Column("worker_type", sa.String(length=100), nullable=False),
        sa.Column("hc", sa.Float(), nullable=False, server_default="0"),
        sa.PrimaryKeyConstraint("mask_id", "worker_type", name="pk_metalization_mask_hc"),
    )


def downgrade() -> None:
    op.drop_table("metalization_mask_hc")
    op.drop_table("moulding_tool_hc")
