from __future__ import annotations

from sqlalchemy import inspect, text

from app.core.config import settings
from app.db.session import get_engine


def _get_columns(inspector, table_name: str) -> list[str]:
    if not inspector.has_table(table_name):
        return []
    return [column["name"] for column in inspector.get_columns(table_name)]


def main() -> None:
    engine = get_engine()
    print(f"database_uri={settings.sqlalchemy_database_uri}")

    inspector = inspect(engine)
    users_columns = _get_columns(inspector, "users")
    champions_columns = _get_columns(inspector, "champions")

    print(f"users.columns={users_columns if users_columns else '<missing table>'}")
    print(f"champions.columns={champions_columns if champions_columns else '<missing table>'}")

    if inspector.has_table("alembic_version"):
        with engine.connect() as connection:
            rows = connection.execute(text("SELECT version_num FROM alembic_version")).fetchall()
        revisions = [str(row[0]) for row in rows]
        print(f"alembic_version={revisions if revisions else '<empty>'}")
    else:
        print("alembic_version=<missing table>")


if __name__ == "__main__":
    main()
