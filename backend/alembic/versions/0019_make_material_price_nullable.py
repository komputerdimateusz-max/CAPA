"""make material price nullable

Revision ID: 0019_make_material_price_nullable
Revises: 0018_add_category_and_make_buy_to_materials
Create Date: 2026-02-13 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "0019_make_material_price_nullable"
down_revision = "0018_add_category_and_make_buy_to_materials"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("materials") as batch_op:
        batch_op.alter_column("price_per_unit", existing_type=sa.Float(), nullable=True)


def downgrade() -> None:
    op.execute(sa.text("UPDATE materials SET price_per_unit = 0 WHERE price_per_unit IS NULL"))
    with op.batch_alter_table("materials") as batch_op:
        batch_op.alter_column("price_per_unit", existing_type=sa.Float(), nullable=False)
