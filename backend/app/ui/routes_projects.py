from __future__ import annotations

from datetime import date, datetime, timedelta
from pathlib import Path

from fastapi import APIRouter, Depends, Form, HTTPException, Query, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.repositories import actions as actions_repo
from app.repositories import projects as projects_repo
from app.services import projects as projects_service
from app.ui.utils import build_action_rows, build_query_params, format_date

router = APIRouter(prefix="/ui", tags=["ui"])

TEMPLATES_DIR = Path(__file__).resolve().parents[1] / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

SORT_OPTIONS = (
    ("due_date", "Due date (oldest first)"),
    ("-due_date", "Due date (newest first)"),
    ("open_actions", "Open actions (least first)"),
    ("-open_actions", "Open actions (most first)"),
)


def _load_project_actions_table(
    db: Session,
    project_id: int,
    only_open: bool,
    only_overdue: bool,
    page: int,
    page_size: int,
) -> dict[str, object]:
    statuses = list(projects_service.OPEN_STATUSES) if (only_open or only_overdue) else None
    due_to = date.today() - timedelta(days=1) if only_overdue else None
    actions, total = actions_repo.list_actions(
        db,
        project_id=project_id,
        statuses=statuses,
        due_to=due_to,
        limit=page_size,
        offset=(page - 1) * page_size,
    )
    subtasks = actions_repo.list_subtasks_for_actions(db, [action.id for action in actions])
    rows = build_action_rows(actions, subtasks)
    total_pages = max(1, (total + page_size - 1) // page_size)
    return {
        "actions": rows,
        "total": total,
        "total_pages": total_pages,
        "page": page,
        "page_size": page_size,
    }


def _load_unassigned_actions(db: Session, query: str | None, limit: int = 25):
    actions, _ = actions_repo.list_actions(
        db,
        unassigned=True,
        query=query,
        limit=limit,
        offset=0,
    )
    return actions


def _manager_context(
    request: Request,
    db: Session,
    *,
    project_id: int,
    action_search: str | None,
    only_open: bool,
    only_overdue: bool,
    page_size: int,
    assignment_feedback: str | None = None,
    assignment_feedback_level: str = "success",
) -> dict[str, object]:
    project = projects_repo.get_project(db, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    table_data = _load_project_actions_table(db, project_id, only_open, only_overdue, 1, page_size)
    filters = {
        "only_open": 1 if only_open else None,
        "only_overdue": 1 if only_overdue else None,
        "page_size": page_size,
    }
    return {
        "request": request,
        "project": project,
        "actions": table_data["actions"],
        "pagination": table_data,
        "filters": filters,
        "query_builder": build_query_params,
        "table_endpoint": f"/ui/projects/{project_id}/_table",
        "assignment_options": _load_unassigned_actions(db, action_search),
        "action_search": action_search or "",
        "assignment_feedback": assignment_feedback,
        "assignment_feedback_level": assignment_feedback_level,
    }


@router.get("/projects", response_class=HTMLResponse, response_model=None)
def projects_list(
    request: Request,
    q: str | None = None,
    status: str | None = None,
    sort: str | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=200),
    db: Session = Depends(get_db),
):
    rollups, total = projects_service.list_projects_with_rollups(
        db,
        query=q,
        status=status,
        sort=sort,
        page=page,
        page_size=page_size,
    )
    total_pages = max(1, (total + page_size - 1) // page_size)
    statuses = projects_repo.list_project_statuses(db)
    filters = {
        "q": q or "",
        "status": status or "",
        "sort": sort or "",
        "page_size": page_size,
    }
    return templates.TemplateResponse(
        "projects_list.html",
        {
            "request": request,
            "projects": rollups,
            "pagination": {
                "total": total,
                "total_pages": total_pages,
                "page": page,
                "page_size": page_size,
            },
            "filters": filters,
            "sort_options": SORT_OPTIONS,
            "status_options": statuses,
            "format_date": format_date,
            "query_builder": build_query_params,
        },
    )


@router.get("/projects/_table", response_class=HTMLResponse, response_model=None)
def projects_table(
    request: Request,
    q: str | None = None,
    status: str | None = None,
    sort: str | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=200),
    db: Session = Depends(get_db),
):
    rollups, total = projects_service.list_projects_with_rollups(
        db,
        query=q,
        status=status,
        sort=sort,
        page=page,
        page_size=page_size,
    )
    total_pages = max(1, (total + page_size - 1) // page_size)
    filters = {
        "q": q or "",
        "status": status or "",
        "sort": sort or "",
        "page_size": page_size,
    }
    return templates.TemplateResponse(
        "partials/projects_table.html",
        {
            "request": request,
            "projects": rollups,
            "pagination": {
                "total": total,
                "total_pages": total_pages,
                "page": page,
                "page_size": page_size,
            },
            "filters": filters,
            "format_date": format_date,
            "query_builder": build_query_params,
        },
    )


@router.get("/projects/{project_id}", response_class=HTMLResponse, response_model=None)
def project_detail(
    project_id: int,
    request: Request,
    only_open: bool = False,
    only_overdue: bool = False,
    action_search: str | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=200),
    db: Session = Depends(get_db),
):
    project = projects_repo.get_project(db, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    kpis = projects_service.get_project_kpis(
        db,
        project_id=project_id,
        only_open=only_open,
        only_overdue=only_overdue,
    )
    table_data = _load_project_actions_table(
        db,
        project_id=project_id,
        only_open=only_open,
        only_overdue=only_overdue,
        page=page,
        page_size=page_size,
    )
    filters = {
        "only_open": 1 if only_open else None,
        "only_overdue": 1 if only_overdue else None,
        "page_size": page_size,
    }
    return templates.TemplateResponse(
        "project_detail.html",
        {
            "request": request,
            "project": project,
            "kpi": kpis,
            "filters": filters,
            "pagination": table_data,
            "actions": table_data["actions"],
            "query_builder": build_query_params,
            "format_date": format_date,
            "table_endpoint": f"/ui/projects/{project_id}/_table",
            "assignment_options": _load_unassigned_actions(db, action_search),
            "action_search": action_search or "",
            "assignment_feedback": None,
            "assignment_feedback_level": "success",
        },
    )


@router.get("/projects/{project_id}/actions-manager", response_class=HTMLResponse, response_model=None)
def project_actions_manager(
    project_id: int,
    request: Request,
    action_search: str | None = None,
    only_open: bool = False,
    only_overdue: bool = False,
    page_size: int = Query(default=25, ge=1, le=200),
    db: Session = Depends(get_db),
):
    return templates.TemplateResponse(
        "partials/project_actions_manager.html",
        _manager_context(
            request,
            db,
            project_id=project_id,
            action_search=action_search,
            only_open=only_open,
            only_overdue=only_overdue,
            page_size=page_size,
        ),
    )


# Manual smoke checklist for regression protection:
# 1) Edit action -> set project -> save -> project shows on action.
# 2) Project screen -> add unassigned action -> it appears in list.
# 3) Remove action from project -> action project becomes null.
# 4) Tags still work, subtasks still work.
@router.post("/projects/{project_id}/actions", response_class=HTMLResponse, response_model=None)
def add_project_action(
    project_id: int,
    request: Request,
    action_id: int = Form(...),
    action_search: str | None = Form(None),
    only_open: bool = Form(False),
    only_overdue: bool = Form(False),
    page_size: int = Form(25),
    db: Session = Depends(get_db),
):
    project = projects_repo.get_project(db, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    action = actions_repo.get_action(db, action_id)
    if not action:
        raise HTTPException(status_code=404, detail="Action not found")

    if action.project_id and action.project_id != project_id:
        existing_project = projects_repo.get_project(db, action.project_id)
        project_label = f"{existing_project.name} ({existing_project.id})" if existing_project else str(action.project_id)
        feedback = f"Action is already assigned to project {project_label}"
        level = "error"
    else:
        action.project_id = project_id
        action.updated_at = datetime.utcnow()
        actions_repo.update_action(db, action)
        feedback = "Action assigned to project."
        level = "success"

    return templates.TemplateResponse(
        "partials/project_actions_manager.html",
        _manager_context(
            request,
            db,
            project_id=project_id,
            action_search=action_search,
            only_open=only_open,
            only_overdue=only_overdue,
            page_size=page_size,
            assignment_feedback=feedback,
            assignment_feedback_level=level,
        ),
    )


@router.post("/projects/{project_id}/actions/{action_id}/remove", response_class=HTMLResponse, response_model=None)
def remove_project_action(
    project_id: int,
    action_id: int,
    request: Request,
    action_search: str | None = Form(None),
    only_open: bool = Form(False),
    only_overdue: bool = Form(False),
    page_size: int = Form(25),
    db: Session = Depends(get_db),
):
    project = projects_repo.get_project(db, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    action = actions_repo.get_action(db, action_id)
    if not action:
        raise HTTPException(status_code=404, detail="Action not found")

    if action.project_id != project_id:
        feedback = "Action is not assigned to this project."
        level = "error"
    else:
        action.project_id = None
        action.updated_at = datetime.utcnow()
        actions_repo.update_action(db, action)
        feedback = "Action unassigned from project."
        level = "success"

    return templates.TemplateResponse(
        "partials/project_actions_manager.html",
        _manager_context(
            request,
            db,
            project_id=project_id,
            action_search=action_search,
            only_open=only_open,
            only_overdue=only_overdue,
            page_size=page_size,
            assignment_feedback=feedback,
            assignment_feedback_level=level,
        ),
    )


@router.get("/projects/{project_id}/_table", response_class=HTMLResponse, response_model=None)
def project_actions_table(
    project_id: int,
    request: Request,
    only_open: bool = False,
    only_overdue: bool = False,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=200),
    db: Session = Depends(get_db),
):
    table_data = _load_project_actions_table(
        db,
        project_id=project_id,
        only_open=only_open,
        only_overdue=only_overdue,
        page=page,
        page_size=page_size,
    )
    filters = {
        "only_open": 1 if only_open else None,
        "only_overdue": 1 if only_overdue else None,
        "page_size": page_size,
    }
    return templates.TemplateResponse(
        "partials/project_actions_table.html",
        {
            "request": request,
            "actions": table_data["actions"],
            "pagination": table_data,
            "filters": filters,
            "query_builder": build_query_params,
            "table_endpoint": f"/ui/projects/{project_id}/_table",
            "project": projects_repo.get_project(db, project_id),
        },
    )
