from __future__ import annotations

import pytest
from sqlalchemy import create_engine, text

from app.main import validate_dev_schema
from app.core.config import settings


def test_validate_dev_schema_raises_clear_message_for_legacy_champions(tmp_path):
    db_path = tmp_path / "legacy.db"
    engine = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})

    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE champions (id INTEGER PRIMARY KEY, name VARCHAR(255) NOT NULL)"))

    with pytest.raises(RuntimeError, match="alembic upgrade head") as exc:
        validate_dev_schema(engine)

    assert "Missing columns on 'champions'" in str(exc.value)


def test_validate_dev_schema_skips_check_outside_dev_mode(tmp_path, monkeypatch):
    db_path = tmp_path / "legacy_non_dev.db"
    engine = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})

    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE champions (id INTEGER PRIMARY KEY, name VARCHAR(255) NOT NULL)"))

    monkeypatch.setattr(settings, "dev_mode", False)
    validate_dev_schema(engine)
