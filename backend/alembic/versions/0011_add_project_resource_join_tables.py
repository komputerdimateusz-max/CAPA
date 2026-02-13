"""add project resource join tables

Revision ID: 0011_add_project_resource_join_tables
Revises: 0010_add_assembly_lines_table
Create Date: 2026-02-13 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "0011_add_project_resource_join_tables"
down_revision = "0010_add_assembly_lines_table"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "project_moulding_tools",
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("tool_id", sa.Integer(), sa.ForeignKey("moulding_tools.id", ondelete="CASCADE"), nullable=False),
        sa.PrimaryKeyConstraint("project_id", "tool_id", name="pk_project_moulding_tools"),
    )
    op.create_index("ix_project_moulding_tools_project_id", "project_moulding_tools", ["project_id"])
    op.create_index("ix_project_moulding_tools_tool_id", "project_moulding_tools", ["tool_id"])

    op.create_table(
        "project_assembly_lines",
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("line_id", sa.Integer(), sa.ForeignKey("assembly_lines.id", ondelete="CASCADE"), nullable=False),
        sa.PrimaryKeyConstraint("project_id", "line_id", name="pk_project_assembly_lines"),
    )
    op.create_index("ix_project_assembly_lines_project_id", "project_assembly_lines", ["project_id"])
    op.create_index("ix_project_assembly_lines_line_id", "project_assembly_lines", ["line_id"])


def downgrade() -> None:
    op.drop_index("ix_project_assembly_lines_line_id", table_name="project_assembly_lines")
    op.drop_index("ix_project_assembly_lines_project_id", table_name="project_assembly_lines")
    op.drop_table("project_assembly_lines")

    op.drop_index("ix_project_moulding_tools_tool_id", table_name="project_moulding_tools")
    op.drop_index("ix_project_moulding_tools_project_id", table_name="project_moulding_tools")
    op.drop_table("project_moulding_tools")
