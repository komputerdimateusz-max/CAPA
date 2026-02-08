from __future__ import annotations

import pytest
from sqlalchemy import create_engine, text

from app.db.schema_guard import validate_dev_schema


@pytest.mark.parametrize(
    "ddl, should_raise",
    [
        (
            """
            CREATE TABLE champions (
                id INTEGER PRIMARY KEY,
                name VARCHAR(255) NOT NULL
            )
            """,
            True,
        ),
        (
            """
            CREATE TABLE champions (
                id INTEGER PRIMARY KEY,
                first_name VARCHAR(150) NOT NULL,
                last_name VARCHAR(150) NOT NULL,
                email VARCHAR(255),
                position VARCHAR(150),
                birth_date DATE
            )
            """,
            False,
        ),
    ],
)
def test_validate_dev_schema_for_champions_columns(tmp_path, ddl: str, should_raise: bool):
    engine = create_engine(f"sqlite:///{tmp_path / 'schema.db'}")
    with engine.begin() as conn:
        conn.execute(text(ddl))

    if should_raise:
        with pytest.raises(RuntimeError, match="Run `alembic upgrade head`"):
            validate_dev_schema(engine)
    else:
        validate_dev_schema(engine)
