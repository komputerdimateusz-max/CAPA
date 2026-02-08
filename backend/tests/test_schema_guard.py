from __future__ import annotations

import pytest
from sqlalchemy import create_engine, text

from app.db.schema_guard import ensure_dev_schema_is_up_to_date


@pytest.mark.parametrize("dev_mode", [True])
def test_schema_guard_raises_when_champion_columns_missing(monkeypatch, dev_mode):
    engine = create_engine("sqlite+pysqlite:///:memory:")
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE champions (id INTEGER PRIMARY KEY, name VARCHAR(255) NOT NULL)"))

    monkeypatch.setattr("app.db.schema_guard.settings.dev_mode", dev_mode)

    with pytest.raises(RuntimeError, match="alembic upgrade head"):
        ensure_dev_schema_is_up_to_date(engine)


@pytest.mark.parametrize("dev_mode", [True, False])
def test_schema_guard_allows_up_to_date_schema(monkeypatch, dev_mode):
    engine = create_engine("sqlite+pysqlite:///:memory:")
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                CREATE TABLE champions (
                    id INTEGER PRIMARY KEY,
                    first_name VARCHAR(150) NOT NULL,
                    last_name VARCHAR(150) NOT NULL,
                    email VARCHAR(255),
                    position VARCHAR(150),
                    birth_date DATE
                )
                """
            )
        )

    monkeypatch.setattr("app.db.schema_guard.settings.dev_mode", dev_mode)
    ensure_dev_schema_is_up_to_date(engine)
