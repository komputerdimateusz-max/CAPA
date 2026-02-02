from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.repositories import actions as actions_repo
from app.repositories import projects as projects_repo
from app.services import projects as projects_service
from app.ui.utils import build_query_params, format_date, build_action_rows

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
        },
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
        },
    )
