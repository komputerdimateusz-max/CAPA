from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.security import hash_password, is_password_too_long
from app.models.user import User

ALLOWED_USER_ROLES = ("viewer", "editor", "admin")


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


def _normalize_required_email(email: str) -> str:
    cleaned = email.strip().lower()
    if not cleaned:
        raise ValueError("Email is required.")
    if "@" not in cleaned:
        raise ValueError("Email must be in a valid format.")
    local, _, domain = cleaned.partition("@")
    if not local or "." not in domain:
        raise ValueError("Email must be in a valid format.")
    return cleaned


def _role_or_default(role: str | None) -> str:
    cleaned = (role or "viewer").strip().lower()
    if cleaned not in ALLOWED_USER_ROLES:
        raise ValueError(f"Role must be one of: {', '.join(ALLOWED_USER_ROLES)}.")
    return cleaned


def _fallback_email_from_username(username: str) -> str:
    normalized = "".join(ch for ch in username.strip().lower() if ch.isalnum() or ch in {".", "_", "-"})
    normalized = normalized or "user"
    return f"{normalized}@local.invalid"


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
    if cleaned_email is None:
        cleaned_email = _fallback_email_from_username(cleaned_username)
    else:
        cleaned_email = _normalize_required_email(cleaned_email)
    _ensure_unique_email(db, cleaned_email, dev_mode)
    user = User(
        username=cleaned_username,
        email=cleaned_email,
        password_hash=hash_password(password),
        role=_role_or_default(role),
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def list_users(db: Session) -> list[User]:
    stmt = select(User).order_by(func.lower(User.email))
    return list(db.execute(stmt).scalars().all())


def upsert_user_role(db: Session, user_id: int, email: str, role: str) -> User:
    cleaned_email = _normalize_required_email(email)
    cleaned_role = _role_or_default(role)
    user = db.get(User, user_id)
    if not user:
        raise ValueError("User not found.")
    user.email = cleaned_email
    user.role = cleaned_role
    db.add(user)
    db.commit()
    db.refresh(user)
    return user
