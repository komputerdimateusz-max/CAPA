from __future__ import annotations

from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.models.project import Project


def list_projects(db: Session, query: str | None = None, status: str | None = None) -> list[Project]:
    stmt = select(Project)
    if query:
        like_query = f"%{query.lower()}%"
        stmt = stmt.where(func.lower(Project.name).like(like_query))
    if status:
        stmt = stmt.where(Project.status == status)
    stmt = stmt.order_by(Project.name.asc())
    return list(db.scalars(stmt).all())


def get_project(db: Session, project_id: int) -> Project | None:
    return db.get(Project, project_id)


def list_project_statuses(db: Session) -> list[str]:
    stmt = (
        select(Project.status)
        .where(Project.status.isnot(None))
        .distinct()
        .order_by(Project.status.asc())
    )
    return [status for status in db.scalars(stmt).all() if status]
