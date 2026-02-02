from __future__ import annotations

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.repositories import actions as actions_repo
from app.schemas.kpi import ActionsKPI
from app.services.kpi import build_actions_kpi

router = APIRouter(prefix="/api/kpi", tags=["kpi"])


@router.get("/actions", response_model=ActionsKPI)
def get_actions_kpi(
    db: Session = Depends(get_db),
    status_filters: Annotated[list[str] | None, Query(alias="status")] = None,
    champion_id: int | None = None,
    champion: str | None = None,
    owner: str | None = None,
    project_id: int | None = None,
    project: str | None = None,
    q: str | None = None,
    tags: list[str] | None = Query(default=None),
    from_date: date | None = Query(default=None, alias="from"),
    to_date: date | None = Query(default=None, alias="to"),
) -> ActionsKPI:
    actions, _total = actions_repo.list_actions(
        db,
        statuses=status_filters,
        champion_id=champion_id,
        champion_name=champion,
        owner=owner,
        project_id=project_id,
        project_name=project,
        query=q,
        tags=tags,
        due_from=from_date,
        due_to=to_date,
        limit=1000,
        offset=0,
    )
    subtasks = actions_repo.list_subtasks_for_actions(db, [action.id for action in actions])
    kpi_payload = build_actions_kpi(actions, subtasks)
    return ActionsKPI(**kpi_payload)
