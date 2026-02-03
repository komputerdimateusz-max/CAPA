from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.security import hash_password, is_password_too_long
from app.models.user import User


def _normalize_username(username: str) -> str:
    cleaned = username.strip()
    if not cleaned:
        raise ValueError("Username is required.")
    return cleaned


def _normalize_email(email: str | None) -> str | None:
    if email is None:
        return None
    cleaned = email.strip()
    return cleaned or None


def _ensure_unique_username(db: Session, username: str, dev_mode: bool) -> None:
    stmt = select(User).where(func.lower(User.username) == username.lower())
    if db.scalar(stmt):
        raise ValueError("Username already exists." if dev_mode else "User already exists.")


def _ensure_unique_email(db: Session, email: str | None, dev_mode: bool) -> None:
    if not email:
        return
    stmt = select(User).where(func.lower(User.email) == email.lower())
    if db.scalar(stmt):
        raise ValueError("Email already exists." if dev_mode else "User already exists.")


def create_user(
    db: Session,
    username: str,
    password: str,
    email: str | None = None,
    role: str = "viewer",
    dev_mode: bool = True,
) -> User:
    cleaned_username = _normalize_username(username)
    cleaned_email = _normalize_email(email)
    if is_password_too_long(password):
        raise ValueError("Password must be 72 bytes or fewer.")
    _ensure_unique_username(db, cleaned_username, dev_mode)
    _ensure_unique_email(db, cleaned_email, dev_mode)
    user = User(
        username=cleaned_username,
        email=cleaned_email,
        password_hash=hash_password(password),
        role=role,
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user
