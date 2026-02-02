from __future__ import annotations

from datetime import date

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.champion import Champion
from app.models.project import Project


def _normalize_name(value: str) -> str:
    return " ".join(value.split()).strip()


def _normalize_optional(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    return cleaned or None


def _normalize_date(value: date | None) -> date | None:
    return value


def create_champion(db: Session, name: str) -> Champion:
    cleaned = _normalize_name(name)
    if not cleaned:
        raise ValueError("Champion name is required.")
    existing = db.scalar(select(Champion).where(func.lower(Champion.name) == cleaned.lower()))
    if existing:
        raise ValueError("Champion already exists.")
    champion = Champion(name=cleaned)
    db.add(champion)
    db.commit()
    db.refresh(champion)
    return champion


def update_champion(db: Session, champion_id: int, name: str) -> Champion:
    cleaned = _normalize_name(name)
    if not cleaned:
        raise ValueError("Champion name is required.")
    champion = db.get(Champion, champion_id)
    if not champion:
        raise ValueError("Champion not found.")
    existing = db.scalar(
        select(Champion)
        .where(func.lower(Champion.name) == cleaned.lower())
        .where(Champion.id != champion_id)
    )
    if existing:
        raise ValueError("Champion already exists.")
    champion.name = cleaned
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
