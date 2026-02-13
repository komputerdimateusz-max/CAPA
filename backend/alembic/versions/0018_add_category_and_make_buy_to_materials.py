"""add category and make_buy to materials

Revision ID: 0018_add_category_and_make_buy_to_materials
Revises: 0017_add_outcome_and_assembly_cost_tables
Create Date: 2026-02-13 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "0018_add_category_and_make_buy_to_materials"
down_revision = "0017_add_outcome_and_assembly_cost_tables"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("materials", sa.Column("category", sa.String(length=100), nullable=True))
    op.add_column("materials", sa.Column("make_buy", sa.Boolean(), nullable=True))

    op.execute(sa.text("UPDATE materials SET category = 'Raw material' WHERE category IS NULL"))
    op.execute(sa.text("UPDATE materials SET make_buy = 0 WHERE make_buy IS NULL"))

    with op.batch_alter_table("materials") as batch_op:
        batch_op.alter_column("category", existing_type=sa.String(length=100), nullable=False)
        batch_op.alter_column("make_buy", existing_type=sa.Boolean(), nullable=False)


def downgrade() -> None:
    with op.batch_alter_table("materials") as batch_op:
        batch_op.drop_column("make_buy")
        batch_op.drop_column("category")
