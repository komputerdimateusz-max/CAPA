from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0009_add_moulding_reference_tables"
down_revision = "0008_harden_users_email_and_role"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "moulding_tools",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True, nullable=False),
        sa.Column("tool_pn", sa.String(length=255), nullable=False),
        sa.Column("description", sa.String(length=500), nullable=True),
        sa.Column("ct_seconds", sa.Float(), nullable=False),
        sa.UniqueConstraint("tool_pn", name="uq_moulding_tools_tool_pn"),
    )

    op.create_table(
        "moulding_machines",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True, nullable=False),
        sa.Column("machine_number", sa.String(length=255), nullable=False),
        sa.Column("tonnage", sa.Integer(), nullable=True),
        sa.UniqueConstraint("machine_number", name="uq_moulding_machines_machine_number"),
    )

    op.create_table(
        "moulding_machine_tools",
        sa.Column("machine_id", sa.Integer(), sa.ForeignKey("moulding_machines.id", ondelete="CASCADE"), nullable=False),
        sa.Column("tool_id", sa.Integer(), sa.ForeignKey("moulding_tools.id", ondelete="CASCADE"), nullable=False),
        sa.PrimaryKeyConstraint("machine_id", "tool_id", name="pk_moulding_machine_tools"),
    )
    op.create_index("ix_moulding_machine_tools_machine_id", "moulding_machine_tools", ["machine_id"], unique=False)
    op.create_index("ix_moulding_machine_tools_tool_id", "moulding_machine_tools", ["tool_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_moulding_machine_tools_tool_id", table_name="moulding_machine_tools")
    op.drop_index("ix_moulding_machine_tools_machine_id", table_name="moulding_machine_tools")
    op.drop_table("moulding_machine_tools")
    op.drop_table("moulding_machines")
    op.drop_table("moulding_tools")
