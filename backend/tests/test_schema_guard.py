from __future__ import annotations

import logging

import pytest
from sqlalchemy import create_engine, text

from app.core.config import settings
from app.main import _build_schema_error_message, validate_dev_schema


def test_validate_dev_schema_logs_and_returns_blocked_result_in_dev_mode(tmp_path, caplog):
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

    with caplog.at_level(logging.ERROR, logger="app.request"):
        result = validate_dev_schema(engine)

    assert not result.is_valid
    assert result.missing_revisions
    assert result.missing_by_table["users"] == ["email"]
    message = _build_schema_error_message(result)
    assert "================= DATABASE SCHEMA ERROR =================" in message
    assert "Database URL:" in message
    assert "Missing Alembic revision(s):" in message
    assert "- users: email" in message
    assert "cd C:\\CAPA\\backend" in message
    assert "call .venv\\Scripts\\activate" in message
    assert "alembic upgrade head" in message
    assert "Application is running in BLOCKED MODE until migrations are applied." in message
    assert any("DATABASE SCHEMA ERROR" in record.message for record in caplog.records)


def test_validate_dev_schema_raises_outside_dev_mode(tmp_path, monkeypatch):
    db_path = tmp_path / "legacy_non_dev.db"
    engine = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})

    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE champions (id INTEGER PRIMARY KEY, name VARCHAR(255) NOT NULL)"))

    monkeypatch.setattr(settings, "dev_mode", False)
    with pytest.raises(RuntimeError, match="BLOCKED MODE"):
        validate_dev_schema(engine)
