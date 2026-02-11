from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.tag import Tag


def list_tags(db: Session) -> list[Tag]:
    stmt = select(Tag).order_by(func.lower(Tag.name).asc())
    return list(db.scalars(stmt).all())


def get_tag(db: Session, tag_id: int) -> Tag | None:
    return db.get(Tag, tag_id)


def get_tag_by_name(db: Session, name: str) -> Tag | None:
    stmt = select(Tag).where(func.lower(Tag.name) == name.strip().lower())
    return db.scalar(stmt)


def create_tag(db: Session, name: str, color: str | None = None) -> Tag:
    tag = Tag(name=name.strip(), color=color.strip() if color else None)
    db.add(tag)
    db.commit()
    db.refresh(tag)
    return tag


def get_or_create_tag(db: Session, name: str, color: str | None = None) -> Tag:
    name = name.strip()
    if not name:
        raise ValueError("Tag name is required")
    existing = get_tag_by_name(db, name)
    if existing:
        return existing
    return create_tag(db, name=name, color=color)
