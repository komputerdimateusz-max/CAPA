from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from app.models.project import Project
from app.services.settings import ALLOWED_PROJECT_STATUSES


def list_projects(db: Session, query: str | None = None, status: str | None = None) -> list[Project]:
    stmt = select(Project).options(
        joinedload(Project.process_engineer),
        joinedload(Project.moulding_tools),
        joinedload(Project.assembly_lines),
    )
    if query:
        like_query = f"%{query.lower()}%"
        stmt = stmt.where(func.lower(Project.name).like(like_query))
    if status:
        stmt = stmt.where(Project.status == status)
    stmt = stmt.order_by(Project.name.asc())
    return list(db.scalars(stmt).unique().all())


def get_project(db: Session, project_id: int) -> Project | None:
    stmt = select(Project).options(
        joinedload(Project.process_engineer),
        joinedload(Project.moulding_tools),
        joinedload(Project.assembly_lines),
    ).where(Project.id == project_id)
    return db.scalar(stmt)


def list_project_statuses(_db: Session) -> list[str]:
    return list(ALLOWED_PROJECT_STATUSES)
