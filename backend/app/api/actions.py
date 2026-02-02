from __future__ import annotations

from datetime import date, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.auth import enforce_action_create_permission, enforce_action_ownership, enforce_write_access, require_auth
from app.db.session import get_db
from app.models.action import Action
from app.models.subtask import Subtask
from app.models.user import User
from app.repositories import actions as actions_repo
from app.schemas.action import ActionCreate, ActionDetailResponse, ActionListResponse, ActionRead, ActionUpdate
from app.schemas.subtask import SubtaskCreate, SubtaskRead, SubtaskUpdate
from app.services.metrics import build_action_metrics

router = APIRouter(prefix="/api/actions", tags=["actions"])


@router.get("", response_model=ActionListResponse)
def list_actions(
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
    sort: str | None = None,
    limit: int = Query(default=200, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
) -> ActionListResponse:
    actions, total = actions_repo.list_actions(
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
        sort=sort,
        limit=limit,
        offset=offset,
    )
    subtasks = actions_repo.list_subtasks_for_actions(db, [action.id for action in actions])
    subtask_map: dict[int, list[Subtask]] = {}
    for subtask in subtasks:
        subtask_map.setdefault(subtask.action_id, []).append(subtask)

    items: list[ActionRead] = []
    for action in actions:
        metrics = build_action_metrics(action, subtask_map.get(action.id, []))
        items.append(
            ActionRead(
                id=action.id,
                title=action.title,
                description=action.description,
                project_id=action.project_id,
                project_name=action.project.name if action.project else None,
                champion_id=action.champion_id,
                champion_name=action.champion.full_name if action.champion else None,
                owner=action.owner,
                status=action.status,
                created_at=action.created_at,
                due_date=action.due_date,
                closed_at=action.closed_at,
                tags=action.tags or [],
                priority=action.priority,
                days_late=metrics.days_late,
                time_to_close_days=metrics.time_to_close_days,
                on_time_close=metrics.on_time_close,
            )
        )

    return ActionListResponse(total=total, items=items)


@router.post("", response_model=ActionDetailResponse, status_code=status.HTTP_201_CREATED)
def create_action(
    payload: ActionCreate,
    db: Session = Depends(get_db),
    user: User | None = Depends(require_auth),
) -> ActionDetailResponse:
    enforce_action_create_permission(user, payload.champion_id)
    action = Action(
        title=payload.title,
        description=payload.description or "",
        project_id=payload.project_id,
        champion_id=payload.champion_id,
        owner=payload.owner,
        status=payload.status,
        created_at=payload.created_at or datetime.utcnow(),
        due_date=payload.due_date,
        closed_at=payload.closed_at,
        tags=payload.tags,
        priority=payload.priority,
    )
    action = actions_repo.create_action(db, action)
    return ActionDetailResponse(
        id=action.id,
        title=action.title,
        description=action.description,
        project_id=action.project_id,
        project_name=action.project.name if action.project else None,
        champion_id=action.champion_id,
        champion_name=action.champion.full_name if action.champion else None,
        owner=action.owner,
        status=action.status,
        created_at=action.created_at,
        due_date=action.due_date,
        closed_at=action.closed_at,
        tags=action.tags or [],
        priority=action.priority,
        days_late=0,
        time_to_close_days=None,
        on_time_close=None,
    )


@router.get("/{action_id}", response_model=ActionDetailResponse)
def get_action(action_id: int, db: Session = Depends(get_db)) -> ActionDetailResponse:
    action = actions_repo.get_action(db, action_id)
    if not action:
        raise HTTPException(status_code=404, detail="Action not found")
    subtasks = actions_repo.list_subtasks(db, action_id)
    metrics = build_action_metrics(action, subtasks)
    return ActionDetailResponse(
        id=action.id,
        title=action.title,
        description=action.description,
        project_id=action.project_id,
        project_name=action.project.name if action.project else None,
        champion_id=action.champion_id,
        champion_name=action.champion.full_name if action.champion else None,
        owner=action.owner,
        status=action.status,
        created_at=action.created_at,
        due_date=action.due_date,
        closed_at=action.closed_at,
        tags=action.tags or [],
        priority=action.priority,
        days_late=metrics.days_late,
        time_to_close_days=metrics.time_to_close_days,
        on_time_close=metrics.on_time_close,
    )


@router.patch("/{action_id}", response_model=ActionDetailResponse)
def update_action(
    action_id: int,
    payload: ActionUpdate,
    db: Session = Depends(get_db),
    user: User | None = Depends(require_auth),
) -> ActionDetailResponse:
    action = actions_repo.get_action(db, action_id)
    if not action:
        raise HTTPException(status_code=404, detail="Action not found")
    enforce_write_access(user)
    enforce_action_ownership(user, action)
    if user and user.role == "champion" and payload.champion_id is not None:
        if payload.champion_id != user.champion_id:
            raise HTTPException(status_code=403, detail="Cannot reassign action ownership")

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(action, field, value)

    action = actions_repo.update_action(db, action)
    subtasks = actions_repo.list_subtasks(db, action_id)
    metrics = build_action_metrics(action, subtasks)
    return ActionDetailResponse(
        id=action.id,
        title=action.title,
        description=action.description,
        project_id=action.project_id,
        project_name=action.project.name if action.project else None,
        champion_id=action.champion_id,
        champion_name=action.champion.full_name if action.champion else None,
        owner=action.owner,
        status=action.status,
        created_at=action.created_at,
        due_date=action.due_date,
        closed_at=action.closed_at,
        tags=action.tags or [],
        priority=action.priority,
        days_late=metrics.days_late,
        time_to_close_days=metrics.time_to_close_days,
        on_time_close=metrics.on_time_close,
    )


@router.delete("/{action_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_action(
    action_id: int,
    db: Session = Depends(get_db),
    user: User | None = Depends(require_auth),
) -> None:
    action = actions_repo.get_action(db, action_id)
    if not action:
        raise HTTPException(status_code=404, detail="Action not found")
    enforce_write_access(user)
    enforce_action_ownership(user, action)
    actions_repo.delete_action(db, action)


@router.get("/{action_id}/subtasks", response_model=list[SubtaskRead])
def list_subtasks(action_id: int, db: Session = Depends(get_db)) -> list[SubtaskRead]:
    action = actions_repo.get_action(db, action_id)
    if not action:
        raise HTTPException(status_code=404, detail="Action not found")
    return [SubtaskRead.model_validate(task) for task in actions_repo.list_subtasks(db, action_id)]


@router.post("/{action_id}/subtasks", response_model=SubtaskRead, status_code=status.HTTP_201_CREATED)
def create_subtask(
    action_id: int,
    payload: SubtaskCreate,
    db: Session = Depends(get_db),
    user: User | None = Depends(require_auth),
) -> SubtaskRead:
    action = actions_repo.get_action(db, action_id)
    if not action:
        raise HTTPException(status_code=404, detail="Action not found")
    enforce_write_access(user)
    enforce_action_ownership(user, action)
    subtask = Subtask(
        action_id=action_id,
        title=payload.title,
        status=payload.status,
        due_date=payload.due_date,
        closed_at=payload.closed_at,
        created_at=payload.created_at or datetime.utcnow(),
    )
    subtask = actions_repo.create_subtask(db, subtask)
    return SubtaskRead.model_validate(subtask)


@router.patch("/subtasks/{subtask_id}", response_model=SubtaskRead)
def update_subtask(
    subtask_id: int,
    payload: SubtaskUpdate,
    db: Session = Depends(get_db),
    user: User | None = Depends(require_auth),
) -> SubtaskRead:
    subtask = actions_repo.get_subtask(db, subtask_id)
    if not subtask:
        raise HTTPException(status_code=404, detail="Subtask not found")
    action = actions_repo.get_action(db, subtask.action_id)
    if not action:
        raise HTTPException(status_code=404, detail="Action not found")
    enforce_write_access(user)
    enforce_action_ownership(user, action)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(subtask, field, value)
    subtask = actions_repo.update_subtask(db, subtask)
    return SubtaskRead.model_validate(subtask)


@router.delete("/subtasks/{subtask_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_subtask(
    subtask_id: int,
    db: Session = Depends(get_db),
    user: User | None = Depends(require_auth),
) -> None:
    subtask = actions_repo.get_subtask(db, subtask_id)
    if not subtask:
        raise HTTPException(status_code=404, detail="Subtask not found")
    action = actions_repo.get_action(db, subtask.action_id)
    if not action:
        raise HTTPException(status_code=404, detail="Action not found")
    enforce_write_access(user)
    enforce_action_ownership(user, action)
    actions_repo.delete_subtask(db, subtask)
