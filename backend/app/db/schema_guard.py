from __future__ import annotations

from collections.abc import Iterable

from sqlalchemy import inspect
from sqlalchemy.engine import Engine


REQUIRED_CHAMPION_COLUMNS = {
    "first_name",
    "last_name",
    "email",
    "position",
    "birth_date",
}


def _format_missing_columns(missing: Iterable[str]) -> str:
    missing_list = ", ".join(sorted(missing))
    return f"Missing columns: {missing_list}."


def ensure_champion_schema(engine: Engine) -> None:
    inspector = inspect(engine)
    if "champions" not in inspector.get_table_names():
        return

    columns = {column["name"] for column in inspector.get_columns("champions")}
    missing = REQUIRED_CHAMPION_COLUMNS - columns
    if missing:
        raise RuntimeError(
            "Database schema is out of date for champions. "
            f"{_format_missing_columns(missing)} "
            "Run `alembic upgrade head` to apply the latest migrations."
        )
