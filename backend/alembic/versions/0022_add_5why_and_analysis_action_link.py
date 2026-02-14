"""add 5why details and analysis-action links

Revision ID: 0022
Revises: 0021_add_action_process_components
Create Date: 2026-02-14
"""

from alembic import op
import sqlalchemy as sa


revision = "0022"
down_revision = "0021_add_action_process_components"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "analysis_5why",
        sa.Column("analysis_id", sa.String(length=64), sa.ForeignKey("analyses.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("problem_statement", sa.Text(), nullable=False),
        sa.Column("where_observed", sa.Text(), nullable=True),
        sa.Column("date_detected", sa.Date(), nullable=True),
        sa.Column("why_1", sa.Text(), nullable=True),
        sa.Column("why_2", sa.Text(), nullable=True),
        sa.Column("why_3", sa.Text(), nullable=True),
        sa.Column("why_4", sa.Text(), nullable=True),
        sa.Column("why_5", sa.Text(), nullable=True),
        sa.Column("root_cause", sa.Text(), nullable=False),
        sa.Column("root_cause_category", sa.String(length=32), nullable=True),
        sa.Column("containment_action", sa.Text(), nullable=True),
        sa.Column("proposed_action", sa.Text(), nullable=True),
    )

    op.create_table(
        "analysis_actions",
        sa.Column("analysis_id", sa.String(length=64), sa.ForeignKey("analyses.id", ondelete="CASCADE"), nullable=False),
        sa.Column("action_id", sa.Integer(), sa.ForeignKey("actions.id", ondelete="CASCADE"), nullable=False),
        sa.PrimaryKeyConstraint("analysis_id", "action_id"),
    )


def downgrade() -> None:
    op.drop_table("analysis_actions")
    op.drop_table("analysis_5why")
