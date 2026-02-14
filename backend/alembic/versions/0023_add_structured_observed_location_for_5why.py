"""add structured observed location for 5why

Revision ID: 0023
Revises: 0022
Create Date: 2026-02-14
"""

from alembic import op
import sqlalchemy as sa


revision = "0023"
down_revision = "0022"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("analysis_5why", sa.Column("observed_process_type", sa.String(length=32), nullable=True))

    op.create_table(
        "analysis_5why_moulding_tools",
        sa.Column("analysis_id", sa.String(length=64), sa.ForeignKey("analyses.id", ondelete="CASCADE"), nullable=False),
        sa.Column("tool_id", sa.Integer(), sa.ForeignKey("moulding_tools.id", ondelete="CASCADE"), nullable=False),
        sa.PrimaryKeyConstraint("analysis_id", "tool_id"),
    )

    op.create_table(
        "analysis_5why_metalization_masks",
        sa.Column("analysis_id", sa.String(length=64), sa.ForeignKey("analyses.id", ondelete="CASCADE"), nullable=False),
        sa.Column("mask_id", sa.Integer(), sa.ForeignKey("metalization_masks.id", ondelete="CASCADE"), nullable=False),
        sa.PrimaryKeyConstraint("analysis_id", "mask_id"),
    )

    op.create_table(
        "analysis_5why_assembly_references",
        sa.Column("analysis_id", sa.String(length=64), sa.ForeignKey("analyses.id", ondelete="CASCADE"), nullable=False),
        sa.Column("reference_id", sa.Integer(), sa.ForeignKey("assembly_line_references.id", ondelete="CASCADE"), nullable=False),
        sa.PrimaryKeyConstraint("analysis_id", "reference_id"),
    )


def downgrade() -> None:
    op.drop_table("analysis_5why_assembly_references")
    op.drop_table("analysis_5why_metalization_masks")
    op.drop_table("analysis_5why_moulding_tools")
    op.drop_column("analysis_5why", "observed_process_type")
