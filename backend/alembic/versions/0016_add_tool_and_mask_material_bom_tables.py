"""add tool and mask material bom tables

Revision ID: 0016_add_tool_and_mask_material_bom_tables
Revises: 0015_add_materials_table
Create Date: 2026-02-13 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "0016_add_tool_and_mask_material_bom_tables"
down_revision = "0015_add_materials_table"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "moulding_tool_materials",
        sa.Column("tool_id", sa.Integer(), nullable=False),
        sa.Column("material_id", sa.Integer(), nullable=False),
        sa.Column("qty_per_piece", sa.Float(), nullable=False),
        sa.ForeignKeyConstraint(["tool_id"], ["moulding_tools.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["material_id"], ["materials.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("tool_id", "material_id"),
        sa.CheckConstraint("qty_per_piece > 0", name="ck_moulding_tool_materials_qty_per_piece_positive"),
    )
    op.create_table(
        "metalization_mask_materials",
        sa.Column("mask_id", sa.Integer(), nullable=False),
        sa.Column("material_id", sa.Integer(), nullable=False),
        sa.Column("qty_per_piece", sa.Float(), nullable=False),
        sa.ForeignKeyConstraint(["mask_id"], ["metalization_masks.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["material_id"], ["materials.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("mask_id", "material_id"),
        sa.CheckConstraint("qty_per_piece > 0", name="ck_metalization_mask_materials_qty_per_piece_positive"),
    )


def downgrade() -> None:
    op.drop_table("metalization_mask_materials")
    op.drop_table("moulding_tool_materials")
