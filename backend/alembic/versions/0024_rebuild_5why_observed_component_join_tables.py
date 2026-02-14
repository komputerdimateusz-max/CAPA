"""rebuild 5why observed component join tables with explicit FKs

Revision ID: 0024
Revises: 0023
Create Date: 2026-02-14
"""

from alembic import op
import sqlalchemy as sa


revision = "0024"
down_revision = "0023"
branch_labels = None
depends_on = None


def _rebuild_join_table(table_name: str, component_column: str, component_fk: str) -> None:
    old_table = f"{table_name}_old"

    op.rename_table(table_name, old_table)

    op.create_table(
        table_name,
        sa.Column("analysis_id", sa.String(length=64), sa.ForeignKey("analyses.id", ondelete="CASCADE"), nullable=False),
        sa.Column(component_column, sa.Integer(), sa.ForeignKey(component_fk, ondelete="CASCADE"), nullable=False),
        sa.PrimaryKeyConstraint("analysis_id", component_column),
    )

    op.execute(
        sa.text(
            f"INSERT INTO {table_name} (analysis_id, {component_column}) "
            f"SELECT analysis_id, {component_column} FROM {old_table}"
        )
    )

    op.drop_table(old_table)


def upgrade() -> None:
    _rebuild_join_table("analysis_5why_moulding_tools", "tool_id", "moulding_tools.id")
    _rebuild_join_table("analysis_5why_metalization_masks", "mask_id", "metalization_masks.id")
    _rebuild_join_table("analysis_5why_assembly_references", "reference_id", "assembly_line_references.id")


def downgrade() -> None:
    _rebuild_join_table("analysis_5why_moulding_tools", "tool_id", "moulding_tools.id")
    _rebuild_join_table("analysis_5why_metalization_masks", "mask_id", "metalization_masks.id")
    _rebuild_join_table("analysis_5why_assembly_references", "reference_id", "assembly_line_references.id")
