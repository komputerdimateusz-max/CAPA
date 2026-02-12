from __future__ import annotations

from datetime import date
from typing import Iterable

from sqlalchemy import Date, case, func, select
from sqlalchemy.orm import selectinload
from sqlalchemy.orm import Session

from app.models.action import Action
from app.models.champion import Champion
from app.models.project import Project
from app.models.subtask import Subtask
from app.models.tag import Tag


DEFAULT_SORT = "created_at_desc"
ALLOWED_SORTS = {
    "created_at_desc",
    "created_at_asc",
    "due_date_asc",
    "due_date_desc",
    "days_late_desc",
    "title_asc",
}


def normalize_sort(sort: str | None) -> str:
    if sort in ALLOWED_SORTS:
        return sort
    return DEFAULT_SORT


def _days_late_expr():
    return case(
        (
            (Action.status != "CLOSED") & Action.due_date.is_not(None),
            func.max(func.julianday(func.current_date()) - func.julianday(Action.due_date), 0),
        ),
        else_=0,
    )


def list_actions(
    db: Session,
    statuses: list[str] | None = None,
    champion_id: int | None = None,
    champion_name: str | None = None,
    owner: str | None = None,
    project_id: int | None = None,
    project_name: str | None = None,
    query: str | None = None,
    unassigned: bool = False,
    tags: list[str] | None = None,
    due_from: date | None = None,
    due_to: date | None = None,
    sort: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> tuple[list[Action], int]:
    stmt = select(Action).options(selectinload(Action.project), selectinload(Action.champion), selectinload(Action.tags))

    if statuses:
        stmt = stmt.where(Action.status.in_(statuses))
    if champion_id is not None:
        stmt = stmt.where(Action.champion_id == champion_id)
    if champion_name:
        champion_full_name = func.lower(func.trim(Champion.first_name + " " + Champion.last_name))
        stmt = stmt.join(Champion, isouter=True).where(
            (champion_full_name == champion_name.lower())
            | (func.lower(Action.owner) == champion_name.lower())
        )
    if owner:
        stmt = stmt.where(Action.owner == owner)
    if project_id is not None:
        stmt = stmt.where(Action.project_id == project_id)
    elif unassigned:
        stmt = stmt.where(Action.project_id.is_(None))
    if project_name:
        stmt = stmt.join(Project, isouter=True).where(func.lower(Project.name) == project_name.lower())
    if query:
        like_query = f"%{query.lower()}%"
        stmt = stmt.where(
            func.lower(Action.title).like(like_query) | func.lower(Action.description).like(like_query)
        )
    if tags:
        for tag in tags:
            stmt = stmt.where(Action.tags.any(func.lower(Tag.name) == tag.lower()))
    if due_from:
        stmt = stmt.where(Action.due_date >= due_from)
    if due_to:
        stmt = stmt.where(Action.due_date <= due_to)

    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0

    normalized_sort = normalize_sort(sort)
    due_date_nulls_last = case((Action.due_date.is_(None), 1), else_=0)

    if normalized_sort == "created_at_asc":
        stmt = stmt.order_by(Action.created_at.asc(), Action.id.asc())
    elif normalized_sort == "due_date_asc":
        stmt = stmt.order_by(due_date_nulls_last.asc(), Action.due_date.asc(), Action.id.desc())
    elif normalized_sort == "due_date_desc":
        stmt = stmt.order_by(due_date_nulls_last.asc(), Action.due_date.desc(), Action.id.desc())
    elif normalized_sort == "days_late_desc":
        stmt = stmt.order_by(_days_late_expr().desc(), Action.id.desc())
    elif normalized_sort == "title_asc":
        stmt = stmt.order_by(func.lower(Action.title).asc(), Action.id.asc())
    else:
        stmt = stmt.order_by(Action.created_at.desc(), Action.id.desc())

    stmt = stmt.limit(limit).offset(offset)

    return list(db.scalars(stmt).all()), total


def list_actions_for_projects(db: Session, project_ids: list[int]) -> list[Action]:
    if not project_ids:
        return []
    stmt = (
        select(Action)
        .options(selectinload(Action.project), selectinload(Action.champion), selectinload(Action.tags))
        .where(Action.project_id.in_(project_ids))
    )
    return list(db.scalars(stmt).all())


def list_actions_created_between(
    db: Session,
    date_from: date | None,
    date_to: date | None,
    project_id: int | None = None,
    champion_id: int | None = None,
) -> list[Action]:
    stmt = select(Action).options(selectinload(Action.project), selectinload(Action.champion), selectinload(Action.tags))
    created_date = func.date(Action.created_at).cast(Date)
    if date_from:
        stmt = stmt.where(created_date >= date_from)
    if date_to:
        stmt = stmt.where(created_date <= date_to)
    if project_id is not None:
        stmt = stmt.where(Action.project_id == project_id)
    if champion_id is not None:
        stmt = stmt.where(Action.champion_id == champion_id)
    stmt = stmt.order_by(Action.created_at.asc())
    return list(db.scalars(stmt).all())


def get_action(db: Session, action_id: int) -> Action | None:
    stmt = select(Action).options(selectinload(Action.project), selectinload(Action.champion), selectinload(Action.tags)).where(Action.id == action_id)
    return db.scalar(stmt)


def list_actions_by_project(db: Session, project_id: int) -> list[Action]:
    stmt = (
        select(Action)
        .options(selectinload(Action.project), selectinload(Action.champion), selectinload(Action.tags))
        .where(Action.project_id == project_id)
        .order_by(Action.id.desc())
    )
    return list(db.scalars(stmt).all())


def create_action(db: Session, action: Action) -> Action:
    db.add(action)
    db.commit()
    db.refresh(action)
    return action


def update_action(db: Session, action: Action) -> Action:
    db.add(action)
    db.commit()
    db.refresh(action)
    return action


def delete_action(db: Session, action: Action) -> None:
    db.delete(action)
    db.commit()


def list_subtasks(db: Session, action_id: int) -> list[Subtask]:
    stmt = select(Subtask).where(Subtask.action_id == action_id).order_by(Subtask.id.asc())
    return list(db.scalars(stmt).all())


def list_subtasks_for_actions(db: Session, action_ids: Iterable[int]) -> list[Subtask]:
    if not action_ids:
        return []
    stmt = select(Subtask).where(Subtask.action_id.in_(list(action_ids)))
    return list(db.scalars(stmt).all())


def create_subtask(db: Session, subtask: Subtask) -> Subtask:
    db.add(subtask)
    db.commit()
    db.refresh(subtask)
    return subtask


def get_subtask(db: Session, subtask_id: int) -> Subtask | None:
    return db.get(Subtask, subtask_id)


def update_subtask(db: Session, subtask: Subtask) -> Subtask:
    db.add(subtask)
    db.commit()
    db.refresh(subtask)
    return subtask


def delete_subtask(db: Session, subtask: Subtask) -> None:
    db.delete(subtask)
    db.commit()
