from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0003_update_champion_fields"
down_revision = "0002_add_users_table"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("champions") as batch:
        batch.add_column(sa.Column("first_name", sa.String(length=150), nullable=True))
        batch.add_column(sa.Column("last_name", sa.String(length=150), nullable=True))
        batch.add_column(sa.Column("email", sa.String(length=255), nullable=True))
        batch.add_column(sa.Column("position", sa.String(length=150), nullable=True))
        batch.add_column(sa.Column("birth_date", sa.Date(), nullable=True))
        batch.create_unique_constraint("uq_champions_email", ["email"])

    connection = op.get_bind()
    rows = connection.execute(sa.text("SELECT id, name FROM champions")).fetchall()
    for row in rows:
        raw_name = (row.name or "").strip()
        parts = raw_name.split()
        if len(parts) >= 2:
            first_name = parts[0]
            last_name = " ".join(parts[1:])
        else:
            first_name = "Unknown"
            last_name = raw_name or "Unknown"
        connection.execute(
            sa.text(
                "UPDATE champions SET first_name = :first_name, last_name = :last_name WHERE id = :id"
            ),
            {"id": row.id, "first_name": first_name, "last_name": last_name},
        )

    with op.batch_alter_table("champions") as batch:
        batch.alter_column("first_name", nullable=False)
        batch.alter_column("last_name", nullable=False)
        # Dropping legacy name column after migrating data to structured fields.
        batch.drop_column("name")


def downgrade() -> None:
    with op.batch_alter_table("champions") as batch:
        batch.add_column(sa.Column("name", sa.String(length=255), nullable=True))

    connection = op.get_bind()
    rows = connection.execute(
        sa.text("SELECT id, first_name, last_name FROM champions")
    ).fetchall()
    for row in rows:
        full_name = f"{row.first_name} {row.last_name}".strip()
        connection.execute(
            sa.text("UPDATE champions SET name = :name WHERE id = :id"),
            {"id": row.id, "name": full_name},
        )

    with op.batch_alter_table("champions") as batch:
        batch.alter_column("name", nullable=False)
        batch.drop_constraint("uq_champions_email", type_="unique")
        batch.drop_column("birth_date")
        batch.drop_column("position")
        batch.drop_column("email")
        batch.drop_column("last_name")
        batch.drop_column("first_name")
