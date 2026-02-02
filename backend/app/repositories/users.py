from __future__ import annotations

from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.models.user import User


def get_user_by_id(db: Session, user_id: int) -> User | None:
    return db.get(User, user_id)


def get_user_by_username(db: Session, username: str) -> User | None:
    stmt = select(User).where(User.username == username)
    return db.execute(stmt).scalar_one_or_none()


def count_users(db: Session) -> int:
    stmt = select(func.count(User.id))
    return db.execute(stmt).scalar_one()


def create_user(db: Session, user: User) -> User:
    db.add(user)
    db.commit()
    db.refresh(user)
    return user
