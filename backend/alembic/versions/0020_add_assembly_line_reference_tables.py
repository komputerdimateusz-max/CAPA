"""add assembly line reference tables

Revision ID: 0020_add_assembly_line_reference_tables
Revises: 0019_make_material_price_nullable
Create Date: 2026-02-13 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "0020_add_assembly_line_reference_tables"
down_revision = "0019_make_material_price_nullable"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "assembly_line_references",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("line_id", sa.Integer(), sa.ForeignKey("assembly_lines.id", ondelete="CASCADE"), nullable=False),
        sa.Column("reference_name", sa.String(length=255), nullable=False),
        sa.Column("fg_material_id", sa.Integer(), sa.ForeignKey("materials.id", ondelete="SET NULL"), nullable=True),
        sa.Column("ct_seconds", sa.Float(), nullable=False),
        sa.UniqueConstraint("line_id", "reference_name", name="uq_assembly_line_reference_name"),
        sa.CheckConstraint("ct_seconds >= 0", name="ck_assembly_line_references_ct_seconds_non_negative"),
    )

    op.create_table(
        "assembly_line_reference_hc",
        sa.Column("reference_id", sa.Integer(), sa.ForeignKey("assembly_line_references.id", ondelete="CASCADE"), nullable=False),
        sa.Column("worker_type", sa.String(length=100), nullable=False),
        sa.Column("hc", sa.Float(), nullable=False),
        sa.PrimaryKeyConstraint("reference_id", "worker_type"),
        sa.CheckConstraint("hc >= 0", name="ck_assembly_line_reference_hc_non_negative"),
    )

    op.create_table(
        "assembly_line_reference_materials_in",
        sa.Column("reference_id", sa.Integer(), sa.ForeignKey("assembly_line_references.id", ondelete="CASCADE"), nullable=False),
        sa.Column("material_id", sa.Integer(), sa.ForeignKey("materials.id", ondelete="CASCADE"), nullable=False),
        sa.Column("qty_per_piece", sa.Float(), nullable=False),
        sa.PrimaryKeyConstraint("reference_id", "material_id"),
        sa.CheckConstraint("qty_per_piece > 0", name="ck_assembly_line_reference_materials_in_qty_positive"),
    )

    op.create_table(
        "assembly_line_reference_materials_out",
        sa.Column("reference_id", sa.Integer(), sa.ForeignKey("assembly_line_references.id", ondelete="CASCADE"), nullable=False),
        sa.Column("material_id", sa.Integer(), sa.ForeignKey("materials.id", ondelete="CASCADE"), nullable=False),
        sa.Column("qty_per_piece", sa.Float(), nullable=False),
        sa.PrimaryKeyConstraint("reference_id", "material_id"),
        sa.CheckConstraint("qty_per_piece > 0", name="ck_assembly_line_reference_materials_out_qty_positive"),
    )


def downgrade() -> None:
    op.drop_table("assembly_line_reference_materials_out")
    op.drop_table("assembly_line_reference_materials_in")
    op.drop_table("assembly_line_reference_hc")
    op.drop_table("assembly_line_references")
