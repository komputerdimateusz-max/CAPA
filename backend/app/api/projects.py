from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.repositories import actions as actions_repo
from app.repositories import projects as projects_repo
from app.schemas.action import ActionRead
from app.schemas.project import ProjectRead
from app.schemas.tag import TagRead
from app.services.metrics import build_action_metrics

router = APIRouter(prefix="/api/projects", tags=["projects"])


def _serialize_action(action, metrics) -> ActionRead:
    return ActionRead(
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
        updated_at=action.updated_at,
        due_date=action.due_date,
        closed_at=action.closed_at,
        tags=[TagRead.model_validate(tag) for tag in action.tags],
        priority=action.priority,
        days_late=metrics.days_late,
        time_to_close_days=metrics.time_to_close_days,
        on_time_close=metrics.on_time_close,
    )


@router.get("", response_model=list[ProjectRead])
def list_projects(db: Session = Depends(get_db)) -> list[ProjectRead]:
    return [ProjectRead.model_validate(project) for project in projects_repo.list_projects(db)]


@router.get("/{project_id}", response_model=ProjectRead)
def get_project(project_id: int, db: Session = Depends(get_db)) -> ProjectRead:
    project = projects_repo.get_project(db, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return ProjectRead.model_validate(project)


@router.get("/{project_id}/actions", response_model=list[ActionRead])
def list_project_actions(project_id: int, db: Session = Depends(get_db)) -> list[ActionRead]:
    project = projects_repo.get_project(db, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    actions = actions_repo.list_actions_by_project(db, project_id)
    subtasks = actions_repo.list_subtasks_for_actions(db, [action.id for action in actions])
    subtask_map: dict[int, list] = {}
    for subtask in subtasks:
        subtask_map.setdefault(subtask.action_id, []).append(subtask)
    return [_serialize_action(action, build_action_metrics(action, subtask_map.get(action.id, []))) for action in actions]


@router.post("/{project_id}/actions/{action_id}", response_model=ActionRead)
def assign_action_to_project(project_id: int, action_id: int, db: Session = Depends(get_db)) -> ActionRead:
    project = projects_repo.get_project(db, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    action = actions_repo.get_action(db, action_id)
    if not action:
        raise HTTPException(status_code=404, detail="Action not found")

    if action.project_id == project_id:
        subtasks = actions_repo.list_subtasks(db, action.id)
        return _serialize_action(action, build_action_metrics(action, subtasks))

    if action.project_id is not None and action.project_id != project_id:
        existing_project = projects_repo.get_project(db, action.project_id)
        project_label = f"{existing_project.name} ({existing_project.id})" if existing_project else str(action.project_id)
        raise HTTPException(status_code=409, detail=f"Action is already assigned to project {project_label}")

    action.project_id = project_id
    action.updated_at = datetime.utcnow()
    action = actions_repo.update_action(db, action)
    subtasks = actions_repo.list_subtasks(db, action.id)
    return _serialize_action(action, build_action_metrics(action, subtasks))


@router.delete("/{project_id}/actions/{action_id}", response_model=ActionRead)
def unassign_action_from_project(project_id: int, action_id: int, db: Session = Depends(get_db)) -> ActionRead:
    project = projects_repo.get_project(db, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    action = actions_repo.get_action(db, action_id)
    if not action:
        raise HTTPException(status_code=404, detail="Action not found")

    if action.project_id != project_id:
        raise HTTPException(status_code=404, detail="Action is not assigned to this project")

    action.project_id = None
    action.updated_at = datetime.utcnow()
    action = actions_repo.update_action(db, action)
    subtasks = actions_repo.list_subtasks(db, action.id)
    return _serialize_action(action, build_action_metrics(action, subtasks))
