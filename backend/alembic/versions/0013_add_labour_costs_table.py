"""add labour costs table

Revision ID: 0013_add_labour_costs_table
Revises: 0012_add_metalization_reference_tables
Create Date: 2026-02-13 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "0013_add_labour_costs_table"
down_revision = "0012_add_metalization_reference_tables"
branch_labels = None
depends_on = None


LABOUR_COST_WORKER_TYPES = ("Operator", "Logistic", "TeamLeader", "Inspector", "Specialist", "Technican")


def upgrade() -> None:
    op.create_table(
        "labour_costs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("worker_type", sa.String(length=100), nullable=False),
        sa.Column("cost_pln", sa.Float(), nullable=False, server_default="0"),
        sa.UniqueConstraint("worker_type", name="uq_labour_costs_worker_type"),
    )

    labour_costs_table = sa.table(
        "labour_costs",
        sa.column("worker_type", sa.String),
        sa.column("cost_pln", sa.Float),
    )
    connection = op.get_bind()
    existing_rows = {
        row[0]
        for row in connection.execute(sa.select(labour_costs_table.c.worker_type)).fetchall()
    }
    for worker_type in LABOUR_COST_WORKER_TYPES:
        if worker_type in existing_rows:
            continue
        op.bulk_insert(
            labour_costs_table,
            [{"worker_type": worker_type, "cost_pln": 0}],
        )



def downgrade() -> None:
    op.drop_table("labour_costs")
