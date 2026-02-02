from __future__ import annotations

from datetime import date
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.champion import Champion
from app.models.project import Project


def _normalize_name(value: str) -> str:
    return " ".join(value.split()).strip()


def _normalize_required(value: str, label: str) -> str:
    cleaned = _normalize_name(value)
    if not cleaned:
        raise ValueError(f"Champion {label} is required.")
    return cleaned


def _normalize_optional(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    return cleaned or None


def _normalize_email(value: str | None) -> str | None:
    cleaned = _normalize_optional(value)
    if not cleaned:
        return None
    if "@" not in cleaned:
        raise ValueError("Champion email must contain @.")
    local, _, domain = cleaned.partition("@")
    if not local or "." not in domain:
        raise ValueError("Champion email must be in a valid format.")
    return cleaned


def _normalize_date(value: date | None) -> date | None:
    return value


def _ensure_unique_full_name(
    db: Session,
    first_name: str,
    last_name: str,
    exclude_id: int | None = None,
) -> None:
    stmt = select(Champion).where(
        func.lower(Champion.first_name) == first_name.lower(),
        func.lower(Champion.last_name) == last_name.lower(),
    )
    if exclude_id is not None:
        stmt = stmt.where(Champion.id != exclude_id)
    if db.scalar(stmt):
        raise ValueError("Champion already exists.")


def _ensure_unique_email(db: Session, email: str | None, exclude_id: int | None = None) -> None:
    if not email:
        return
    stmt = select(Champion).where(func.lower(Champion.email) == email.lower())
    if exclude_id is not None:
        stmt = stmt.where(Champion.id != exclude_id)
    if db.scalar(stmt):
        raise ValueError("Champion email already exists.")


def create_champion(
    db: Session,
    first_name: str,
    last_name: str,
    email: str | None,
    position: str | None,
    birth_date: date | None,
) -> Champion:
    cleaned_first = _normalize_required(first_name, "first name")
    cleaned_last = _normalize_required(last_name, "last name")
    cleaned_email = _normalize_email(email)
    cleaned_position = _normalize_optional(position)
    _ensure_unique_full_name(db, cleaned_first, cleaned_last)
    _ensure_unique_email(db, cleaned_email)
    champion = Champion(
        first_name=cleaned_first,
        last_name=cleaned_last,
        email=cleaned_email,
        position=cleaned_position,
        birth_date=_normalize_date(birth_date),
    )
    db.add(champion)
    db.commit()
    db.refresh(champion)
    return champion


def update_champion(
    db: Session,
    champion_id: int,
    first_name: str,
    last_name: str,
    email: str | None,
    position: str | None,
    birth_date: date | None,
) -> Champion:
    cleaned_first = _normalize_required(first_name, "first name")
    cleaned_last = _normalize_required(last_name, "last name")
    cleaned_email = _normalize_email(email)
    cleaned_position = _normalize_optional(position)
    champion = db.get(Champion, champion_id)
    if not champion:
        raise ValueError("Champion not found.")
    _ensure_unique_full_name(db, cleaned_first, cleaned_last, exclude_id=champion_id)
    _ensure_unique_email(db, cleaned_email, exclude_id=champion_id)
    champion.first_name = cleaned_first
    champion.last_name = cleaned_last
    champion.email = cleaned_email
    champion.position = cleaned_position
    champion.birth_date = _normalize_date(birth_date)
    db.add(champion)
    db.commit()
    db.refresh(champion)
    return champion


def create_project(
    db: Session,
    name: str,
    status: str | None,
    due_date: date | None,
) -> Project:
    cleaned = _normalize_name(name)
    if not cleaned:
        raise ValueError("Project name is required.")
    existing = db.scalar(select(Project).where(func.lower(Project.name) == cleaned.lower()))
    if existing:
        raise ValueError("Project already exists.")
    project = Project(
        name=cleaned,
        status=_normalize_optional(status),
        due_date=_normalize_date(due_date),
    )
    db.add(project)
    db.commit()
    db.refresh(project)
    return project


def update_project(
    db: Session,
    project_id: int,
    name: str,
    status: str | None,
    due_date: date | None,
) -> Project:
    cleaned = _normalize_name(name)
    if not cleaned:
        raise ValueError("Project name is required.")
    project = db.get(Project, project_id)
    if not project:
        raise ValueError("Project not found.")
    existing = db.scalar(
        select(Project)
        .where(func.lower(Project.name) == cleaned.lower())
        .where(Project.id != project_id)
    )
    if existing:
        raise ValueError("Project already exists.")
    project.name = cleaned
    project.status = _normalize_optional(status)
    project.due_date = _normalize_date(due_date)
    db.add(project)
    db.commit()
    db.refresh(project)
    return project
