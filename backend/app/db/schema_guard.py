from __future__ import annotations

from sqlalchemy import Engine, inspect

from app.core.config import settings

_REQUIRED_CHAMPION_COLUMNS = {
    "first_name",
    "last_name",
    "email",
    "position",
    "birth_date",
}


def ensure_dev_schema_is_up_to_date(engine: Engine) -> None:
    """Fail fast in dev if local DB schema is behind ORM expectations."""

    if not settings.dev_mode:
        return

    inspector = inspect(engine)
    table_names = set(inspector.get_table_names())
    if "champions" not in table_names:
        return

    current_columns = {column["name"] for column in inspector.get_columns("champions")}
    missing_columns = sorted(_REQUIRED_CHAMPION_COLUMNS - current_columns)
    if not missing_columns:
        return

    missing_columns_text = ", ".join(missing_columns)
    raise RuntimeError(
        "Database schema is behind the application models. "
        "Missing columns in 'champions': "
        f"{missing_columns_text}. "
        "Run 'alembic upgrade head' in the backend directory and restart the server."
    )
