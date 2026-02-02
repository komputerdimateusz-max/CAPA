from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

from sqlalchemy.orm import Session

from app.models.project import Project
from app.repositories import actions as actions_repo
from app.repositories import projects as projects_repo
from app.services.kpi import build_actions_kpi
from app.services.metrics import calculate_action_days_late

OPEN_STATUSES = ("OPEN", "IN_PROGRESS", "BLOCKED")


@dataclass(frozen=True)
class ProjectRollup:
    project: Project
    open_actions: int
    overdue_actions: int
    sum_days_late: int


def list_projects_with_rollups(
    db: Session,
    query: str | None = None,
    status: str | None = None,
    sort: str | None = None,
    page: int = 1,
    page_size: int = 25,
) -> tuple[list[ProjectRollup], int]:
    projects = projects_repo.list_projects(db, query=query, status=status)
    total = len(projects)
    if not projects:
        return [], 0

    project_ids = [project.id for project in projects]
    actions = actions_repo.list_actions_for_projects(db, project_ids)
    subtasks = actions_repo.list_subtasks_for_actions(db, [action.id for action in actions])
    subtask_map: dict[int, list] = {}
    for subtask in subtasks:
        subtask_map.setdefault(subtask.action_id, []).append(subtask)

    today = date.today()
    rollups: list[ProjectRollup] = []
    actions_by_project: dict[int, list] = {project_id: [] for project_id in project_ids}
    for action in actions:
        if action.project_id is not None:
            actions_by_project.setdefault(action.project_id, []).append(action)

    for project in projects:
        project_actions = actions_by_project.get(project.id, [])
        open_count = 0
        overdue_count = 0
        sum_days_late = 0
        for action in project_actions:
            is_open = action.status.upper() != "CLOSED"
            if is_open:
                open_count += 1
                if action.due_date and action.due_date < today:
                    overdue_count += 1
            sum_days_late += calculate_action_days_late(action, subtask_map.get(action.id, []), today=today)
        rollups.append(
            ProjectRollup(
                project=project,
                open_actions=open_count,
                overdue_actions=overdue_count,
                sum_days_late=sum_days_late,
            )
        )

    if sort in {"due_date", "-due_date"}:
        reverse = sort == "-due_date"

        def due_key(item: ProjectRollup):
            due = item.project.due_date
            if due is None:
                return (1, date.min)
            return (0, due)

        rollups.sort(key=due_key, reverse=reverse)
    elif sort in {"open_actions", "-open_actions"}:
        reverse = sort == "-open_actions"
        rollups.sort(key=lambda item: item.open_actions, reverse=reverse)
    else:
        rollups.sort(key=lambda item: (item.project.name or "").lower())

    start = (page - 1) * page_size
    end = start + page_size
    return rollups[start:end], total


def get_project_kpis(
    db: Session,
    project_id: int,
    only_open: bool = False,
    only_overdue: bool = False,
) -> dict[str, float | int]:
    statuses = list(OPEN_STATUSES) if (only_open or only_overdue) else None
    due_to = None
    if only_overdue:
        due_to = date.today() - timedelta(days=1)
    actions, _total = actions_repo.list_actions(
        db,
        statuses=statuses,
        project_id=project_id,
        due_to=due_to,
        limit=10000,
        offset=0,
    )
    subtasks = actions_repo.list_subtasks_for_actions(db, [action.id for action in actions])
    return build_actions_kpi(actions, subtasks)
