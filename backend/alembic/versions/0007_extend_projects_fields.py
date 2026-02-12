from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0007_extend_projects_fields"
down_revision = "0006_add_actions_updated_at"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("projects") as batch_op:
        batch_op.add_column(sa.Column("max_volume", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("flex_percent", sa.Float(), nullable=True))
        batch_op.add_column(sa.Column("process_engineer_id", sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            "fk_projects_process_engineer_id_champions",
            "champions",
            ["process_engineer_id"],
            ["id"],
        )


def downgrade() -> None:
    with op.batch_alter_table("projects") as batch_op:
        batch_op.drop_constraint("fk_projects_process_engineer_id_champions", type_="foreignkey")
        batch_op.drop_column("process_engineer_id")
        batch_op.drop_column("flex_percent")
        batch_op.drop_column("max_volume")
