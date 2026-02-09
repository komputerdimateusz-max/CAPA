from __future__ import annotations

import pytest
from sqlalchemy import create_engine, text

from app.main import validate_dev_schema
from app.core.config import settings


def test_validate_dev_schema_raises_clear_message_for_legacy_schema(tmp_path):
    db_path = tmp_path / "legacy.db"
    engine = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})

    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE champions (id INTEGER PRIMARY KEY, name VARCHAR(255) NOT NULL)"))
        connection.execute(
            text(
                "CREATE TABLE users ("
                "id INTEGER PRIMARY KEY, "
                "username VARCHAR(150) NOT NULL, "
                "password_hash VARCHAR(255) NOT NULL, "
                "role VARCHAR(50) NOT NULL, "
                "is_active BOOLEAN NOT NULL"
                ")"
            )
        )

    with pytest.raises(RuntimeError, match="alembic upgrade head") as exc:
        validate_dev_schema(engine)

    assert "Missing columns -> champions" in str(exc.value)
    assert "users: email" in str(exc.value)


def test_validate_dev_schema_skips_check_outside_dev_mode(tmp_path, monkeypatch):
    db_path = tmp_path / "legacy_non_dev.db"
    engine = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})

    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE champions (id INTEGER PRIMARY KEY, name VARCHAR(255) NOT NULL)"))

    monkeypatch.setattr(settings, "dev_mode", False)
    validate_dev_schema(engine)
