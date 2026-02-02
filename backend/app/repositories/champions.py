from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.champion import Champion


def list_champions(db: Session) -> list[Champion]:
    stmt = select(Champion).order_by(Champion.name.asc())
    return list(db.scalars(stmt).all())


def get_champion(db: Session, champion_id: int) -> Champion | None:
    return db.get(Champion, champion_id)
