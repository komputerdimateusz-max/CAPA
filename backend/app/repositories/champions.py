from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.champion import Champion


def list_champions(
    db: Session,
    *,
    active_only: bool = True,
    include_ids: list[int] | None = None,
) -> list[Champion]:
    stmt = select(Champion)
    if active_only:
        if include_ids:
            stmt = stmt.where((Champion.is_active.is_(True)) | (Champion.id.in_(include_ids)))
        else:
            stmt = stmt.where(Champion.is_active.is_(True))
    stmt = stmt.order_by(Champion.last_name.asc(), Champion.first_name.asc())
    return list(db.scalars(stmt).all())


def deactivate_champion(db: Session, champion_id: int) -> Champion | None:
    champion = db.get(Champion, champion_id)
    if champion is None:
        return None
    champion.is_active = False
    db.add(champion)
    db.commit()
    db.refresh(champion)
    return champion


def get_champion(db: Session, champion_id: int) -> Champion | None:
    return db.get(Champion, champion_id)
