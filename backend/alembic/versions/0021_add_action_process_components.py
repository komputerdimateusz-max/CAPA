"""add action process type and component join tables

Revision ID: 0021_add_action_process_components
Revises: 0020_add_assembly_line_reference_tables
Create Date: 2026-02-14 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "0021_add_action_process_components"
down_revision = "0020_add_assembly_line_reference_tables"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("actions", sa.Column("process_type", sa.String(length=32), nullable=True))

    op.create_table(
        "action_moulding_tools",
        sa.Column("action_id", sa.Integer(), sa.ForeignKey("actions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("tool_id", sa.Integer(), sa.ForeignKey("moulding_tools.id", ondelete="CASCADE"), nullable=False),
        sa.PrimaryKeyConstraint("action_id", "tool_id"),
    )

    op.create_table(
        "action_metalization_masks",
        sa.Column("action_id", sa.Integer(), sa.ForeignKey("actions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("mask_id", sa.Integer(), sa.ForeignKey("metalization_masks.id", ondelete="CASCADE"), nullable=False),
        sa.PrimaryKeyConstraint("action_id", "mask_id"),
    )

    op.create_table(
        "action_assembly_references",
        sa.Column("action_id", sa.Integer(), sa.ForeignKey("actions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("reference_id", sa.Integer(), sa.ForeignKey("assembly_line_references.id", ondelete="CASCADE"), nullable=False),
        sa.PrimaryKeyConstraint("action_id", "reference_id"),
    )


def downgrade() -> None:
    op.drop_table("action_assembly_references")
    op.drop_table("action_metalization_masks")
    op.drop_table("action_moulding_tools")
    op.drop_column("actions", "process_type")
