"""add metalization reference tables

Revision ID: 0012_add_metalization_reference_tables
Revises: 0011_add_project_resource_join_tables
Create Date: 2026-02-13 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "0012_add_metalization_reference_tables"
down_revision = "0011_add_project_resource_join_tables"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "metalization_masks",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("mask_pn", sa.String(length=255), nullable=False),
        sa.Column("description", sa.String(length=500), nullable=True),
        sa.Column("ct_seconds", sa.Float(), nullable=False),
        sa.UniqueConstraint("mask_pn", name="uq_metalization_masks_mask_pn"),
    )

    op.create_table(
        "metalization_chambers",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("chamber_number", sa.String(length=255), nullable=False),
        sa.UniqueConstraint("chamber_number", name="uq_metalization_chambers_chamber_number"),
    )

    op.create_table(
        "metalization_chamber_masks",
        sa.Column("chamber_id", sa.Integer(), sa.ForeignKey("metalization_chambers.id", ondelete="CASCADE"), nullable=False),
        sa.Column("mask_id", sa.Integer(), sa.ForeignKey("metalization_masks.id", ondelete="CASCADE"), nullable=False),
        sa.PrimaryKeyConstraint("chamber_id", "mask_id", name="pk_metalization_chamber_masks"),
    )
    op.create_index("ix_metalization_chamber_masks_chamber_id", "metalization_chamber_masks", ["chamber_id"])
    op.create_index("ix_metalization_chamber_masks_mask_id", "metalization_chamber_masks", ["mask_id"])

    op.create_table(
        "project_metalization_masks",
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("mask_id", sa.Integer(), sa.ForeignKey("metalization_masks.id", ondelete="CASCADE"), nullable=False),
        sa.PrimaryKeyConstraint("project_id", "mask_id", name="pk_project_metalization_masks"),
    )
    op.create_index("ix_project_metalization_masks_project_id", "project_metalization_masks", ["project_id"])
    op.create_index("ix_project_metalization_masks_mask_id", "project_metalization_masks", ["mask_id"])


def downgrade() -> None:
    op.drop_index("ix_project_metalization_masks_mask_id", table_name="project_metalization_masks")
    op.drop_index("ix_project_metalization_masks_project_id", table_name="project_metalization_masks")
    op.drop_table("project_metalization_masks")

    op.drop_index("ix_metalization_chamber_masks_mask_id", table_name="metalization_chamber_masks")
    op.drop_index("ix_metalization_chamber_masks_chamber_id", table_name="metalization_chamber_masks")
    op.drop_table("metalization_chamber_masks")

    op.drop_table("metalization_chambers")
    op.drop_table("metalization_masks")
