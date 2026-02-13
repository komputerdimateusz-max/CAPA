"""add outcome and assembly cost tables

Revision ID: 0017_add_outcome_and_assembly_cost_tables
Revises: 0016_add_tool_and_mask_material_bom_tables
Create Date: 2026-02-13 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "0017_add_outcome_and_assembly_cost_tables"
down_revision = "0016_add_tool_and_mask_material_bom_tables"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "moulding_tool_materials_out",
        sa.Column("tool_id", sa.Integer(), nullable=False),
        sa.Column("material_id", sa.Integer(), nullable=False),
        sa.Column("qty_per_piece", sa.Float(), nullable=False),
        sa.ForeignKeyConstraint(["tool_id"], ["moulding_tools.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["material_id"], ["materials.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("tool_id", "material_id"),
        sa.CheckConstraint("qty_per_piece > 0", name="ck_moulding_tool_materials_out_qty_per_piece_positive"),
    )
    op.create_table(
        "metalization_mask_materials_out",
        sa.Column("mask_id", sa.Integer(), nullable=False),
        sa.Column("material_id", sa.Integer(), nullable=False),
        sa.Column("qty_per_piece", sa.Float(), nullable=False),
        sa.ForeignKeyConstraint(["mask_id"], ["metalization_masks.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["material_id"], ["materials.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("mask_id", "material_id"),
        sa.CheckConstraint("qty_per_piece > 0", name="ck_metalization_mask_materials_out_qty_per_piece_positive"),
    )
    op.create_table(
        "assembly_line_hc",
        sa.Column("line_id", sa.Integer(), sa.ForeignKey("assembly_lines.id", ondelete="CASCADE"), nullable=False),
        sa.Column("worker_type", sa.String(length=100), nullable=False),
        sa.Column("hc", sa.Float(), nullable=False, server_default="0"),
        sa.PrimaryKeyConstraint("line_id", "worker_type", name="pk_assembly_line_hc"),
    )
    op.create_table(
        "assembly_line_materials_in",
        sa.Column("line_id", sa.Integer(), nullable=False),
        sa.Column("material_id", sa.Integer(), nullable=False),
        sa.Column("qty_per_piece", sa.Float(), nullable=False),
        sa.ForeignKeyConstraint(["line_id"], ["assembly_lines.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["material_id"], ["materials.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("line_id", "material_id"),
        sa.CheckConstraint("qty_per_piece > 0", name="ck_assembly_line_materials_in_qty_per_piece_positive"),
    )
    op.create_table(
        "assembly_line_materials_out",
        sa.Column("line_id", sa.Integer(), nullable=False),
        sa.Column("material_id", sa.Integer(), nullable=False),
        sa.Column("qty_per_piece", sa.Float(), nullable=False),
        sa.ForeignKeyConstraint(["line_id"], ["assembly_lines.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["material_id"], ["materials.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("line_id", "material_id"),
        sa.CheckConstraint("qty_per_piece > 0", name="ck_assembly_line_materials_out_qty_per_piece_positive"),
    )

    conn = op.get_bind()
    rows = conn.execute(sa.text("SELECT id, hc FROM assembly_lines")).fetchall()
    for line_id, hc in rows:
        conn.execute(
            sa.text(
                "INSERT INTO assembly_line_hc (line_id, worker_type, hc) VALUES (:line_id, 'Operator', :hc)"
            ),
            {"line_id": line_id, "hc": float(hc or 0)},
        )


def downgrade() -> None:
    op.drop_table("assembly_line_materials_out")
    op.drop_table("assembly_line_materials_in")
    op.drop_table("assembly_line_hc")
    op.drop_table("metalization_mask_materials_out")
    op.drop_table("moulding_tool_materials_out")
