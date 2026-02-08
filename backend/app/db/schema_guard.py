from __future__ import annotations

from collections.abc import Iterable

from sqlalchemy import inspect
from sqlalchemy.engine import Engine

from app.core.config import settings

_REQUIRED_CHAMPION_COLUMNS = {
    "first_name",
    "last_name",
    "email",
    "position",
    "birth_date",
}


def _missing_columns(engine: Engine, table_name: str, required_columns: Iterable[str]) -> set[str]:
    inspector = inspect(engine)
    tables = set(inspector.get_table_names())
    if table_name not in tables:
        return set()
    existing_columns = {column["name"] for column in inspector.get_columns(table_name)}
    return set(required_columns) - existing_columns


def validate_dev_schema(engine: Engine) -> None:
    """Fail fast in dev mode when local DB schema is behind expected migrations."""
    if not settings.dev_mode:
        return

    missing_columns = _missing_columns(engine, "champions", _REQUIRED_CHAMPION_COLUMNS)
    if not missing_columns:
        return

    missing_list = ", ".join(sorted(missing_columns))
    raise RuntimeError(
        "Database schema is out of date for table 'champions'. "
        f"Missing columns: {missing_list}. "
        "Run `alembic upgrade head` from the backend directory and restart the server."
    )
