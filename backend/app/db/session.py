from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings


def get_engine():
    return create_engine(
        settings.sqlalchemy_database_uri,
        connect_args={"check_same_thread": False} if settings.sqlalchemy_database_uri.startswith("sqlite") else {},
    )


SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=get_engine())


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
