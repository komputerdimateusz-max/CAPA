from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.project import Project


def list_projects(db: Session) -> list[Project]:
    stmt = select(Project).order_by(Project.name.asc())
    return list(db.scalars(stmt).all())


def get_project(db: Session, project_id: int) -> Project | None:
    return db.get(Project, project_id)
