from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0010_add_assembly_lines_table"
down_revision = "0009_add_moulding_reference_tables"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "assembly_lines",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True, nullable=False),
        sa.Column("line_number", sa.String(length=255), nullable=False),
        sa.Column("ct_seconds", sa.Float(), nullable=False),
        sa.Column("hc", sa.Integer(), nullable=False),
        sa.UniqueConstraint("line_number", name="uq_assembly_lines_line_number"),
    )


def downgrade() -> None:
    op.drop_table("assembly_lines")
