from __future__ import annotations

from datetime import date, datetime
import logging
from pathlib import Path
from fastapi import APIRouter, Depends, Form, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.core.auth import enforce_action_create_permission, enforce_action_ownership, enforce_write_access
from app.db.session import get_db
from app.models.action import Action
from app.models.subtask import Subtask
from app.repositories import actions as actions_repo
from app.repositories import champions as champions_repo
from app.repositories import projects as projects_repo
from app.services.kpi import build_actions_kpi
from app.services.metrics import calculate_action_days_late
from app.ui.utils import build_action_rows, build_query_params, format_date

router = APIRouter(prefix="/ui", tags=["ui"])

TEMPLATES_DIR = Path(__file__).resolve().parents[1] / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))
MAX_KPI_ACTIONS = 10000
SORT_OPTIONS = (
    ("due_date", "Due date (oldest first)"),
    ("-due_date", "Due date (newest first)"),
    ("created_at", "Created (oldest first)"),
    ("-created_at", "Created (newest first)"),
    ("days_late", "Days late (least first)"),
    ("-days_late", "Days late (most first)"),
)
STATUS_OPTIONS = ("OPEN", "IN_PROGRESS", "BLOCKED", "CLOSED")
logger = logging.getLogger("app.ui")


def _html_fallback_page(title: str, message: str, status_code: int = 500) -> HTMLResponse:
    body = (
        "<!doctype html>"
        "<html lang='en'><head><meta charset='utf-8'><title>"
        f"{title}"
        "</title></head><body>"
        f"<h1>{title}</h1><p>{message}</p>"
        "<p><a href='/ui/login'>Go to Login</a></p>"
        "</body></html>"
    )
    return HTMLResponse(content=body, status_code=status_code)


def _parse_tags(tags: str | None) -> list[str] | None:
    if not tags:
        return None
    parsed = [tag.strip() for tag in tags.split(",") if tag.strip()]
    return parsed or None


def _parse_optional_date(value: str | None) -> date | None:
    if not value:
        return None
    return date.fromisoformat(value)


def _parse_optional_int(value: str | None) -> int | None:
    if not value:
        return None
    return int(value)


def _current_user(request: Request):
    return getattr(request.state, "user", None)


def _load_kpi_data(
    db: Session,
    status_filters: list[str] | None,
    champion_id: int | None,
    project_id: int | None,
    query: str | None,
    tags: list[str] | None,
    due_from: date | None,
    due_to: date | None,
) -> dict[str, float | int]:
    actions, _total = actions_repo.list_actions(
        db,
        statuses=status_filters,
        champion_id=champion_id,
        project_id=project_id,
        query=query,
        tags=tags,
        due_from=due_from,
        due_to=due_to,
        limit=MAX_KPI_ACTIONS,
        offset=0,
    )
    subtasks = actions_repo.list_subtasks_for_actions(db, [action.id for action in actions])
    return build_actions_kpi(actions, subtasks)


def _load_actions_table(
    db: Session,
    status_filters: list[str] | None,
    champion_id: int | None,
    project_id: int | None,
    query: str | None,
    tags: list[str] | None,
    due_from: date | None,
    due_to: date | None,
    sort: str | None,
    page: int,
    page_size: int,
) -> dict[str, object]:
    if sort in {"days_late", "-days_late"}:
        actions, _total = actions_repo.list_actions(
            db,
            statuses=status_filters,
            champion_id=champion_id,
            project_id=project_id,
            query=query,
            tags=tags,
            due_from=due_from,
            due_to=due_to,
            limit=MAX_KPI_ACTIONS,
            offset=0,
        )
        subtasks = actions_repo.list_subtasks_for_actions(db, [action.id for action in actions])
        rows = build_action_rows(actions, subtasks)
        reverse = sort == "-days_late"
        rows.sort(key=lambda row: row["days_late"], reverse=reverse)
        total = len(rows)
        start = (page - 1) * page_size
        end = start + page_size
        page_rows = rows[start:end]
    else:
        actions, total = actions_repo.list_actions(
            db,
            statuses=status_filters,
            champion_id=champion_id,
            project_id=project_id,
            query=query,
            tags=tags,
            due_from=due_from,
            due_to=due_to,
            sort=sort,
            limit=page_size,
            offset=(page - 1) * page_size,
        )
        subtasks = actions_repo.list_subtasks_for_actions(db, [action.id for action in actions])
        page_rows = build_action_rows(actions, subtasks)

    total_pages = max(1, (total + page_size - 1) // page_size)
    return {
        "actions": page_rows,
        "total": total,
        "total_pages": total_pages,
        "page": page,
        "page_size": page_size,
    }


def _render_subtasks(
    request: Request,
    action: Action,
    subtasks: list[Subtask],
):
    return templates.TemplateResponse(
        "partials/subtasks.html",
        {
            "request": request,
            "action": action,
            "subtasks": subtasks,
            "format_date": format_date,
        },
    )


@router.get("", response_class=HTMLResponse, response_model=None)
def ui_index(request: Request):
    try:
        if not getattr(request.state, "user", None):
            return RedirectResponse(url="/login", status_code=302)
        return templates.TemplateResponse("ui_index.html", {"request": request})
    except Exception:
        logger.exception("Failed to render /ui")
        return _html_fallback_page(
            title="CAPA UI Error",
            message="The UI failed to render. Please check server logs for details.",
            status_code=500,
        )


@router.get("/actions", response_class=HTMLResponse, response_model=None)
def actions_list(
    request: Request,
    deleted: int | None = None,
    status_filters: list[str] | None = Query(default=None, alias="status"),
    champion_id: int | None = None,
    project_id: int | None = None,
    q: str | None = None,
    tags: str | None = None,
    from_date: date | None = Query(default=None, alias="from"),
    to_date: date | None = Query(default=None, alias="to"),
    sort: str | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=200),
    db: Session = Depends(get_db),
):
    parsed_tags = _parse_tags(tags)
    table_data = _load_actions_table(
        db,
        status_filters=status_filters,
        champion_id=champion_id,
        project_id=project_id,
        query=q,
        tags=parsed_tags,
        due_from=from_date,
        due_to=to_date,
        sort=sort,
        page=page,
        page_size=page_size,
    )
    kpi = _load_kpi_data(
        db,
        status_filters=status_filters,
        champion_id=champion_id,
        project_id=project_id,
        query=q,
        tags=parsed_tags,
        due_from=from_date,
        due_to=to_date,
    )
    projects = projects_repo.list_projects(db)
    champions = champions_repo.list_champions(db)
    filters = {
        "q": q or "",
        "status": status_filters or [],
        "project_id": project_id,
        "champion_id": champion_id,
        "tags": tags or "",
        "from": from_date.isoformat() if from_date else "",
        "to": to_date.isoformat() if to_date else "",
        "sort": sort or "",
        "page_size": page_size,
    }
    return templates.TemplateResponse(
        "actions_list.html",
        {
            "request": request,
            "actions": table_data["actions"],
            "kpi": kpi,
            "deleted": bool(deleted),
            "filters": filters,
            "projects": projects,
            "champions": champions,
            "status_options": STATUS_OPTIONS,
            "sort_options": SORT_OPTIONS,
            "pagination": table_data,
            "query_builder": build_query_params,
        },
    )


@router.get("/actions/_table", response_class=HTMLResponse, response_model=None)
def actions_table(
    request: Request,
    status_filters: list[str] | None = Query(default=None, alias="status"),
    champion_id: int | None = None,
    project_id: int | None = None,
    q: str | None = None,
    tags: str | None = None,
    from_date: date | None = Query(default=None, alias="from"),
    to_date: date | None = Query(default=None, alias="to"),
    sort: str | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=200),
    db: Session = Depends(get_db),
):
    parsed_tags = _parse_tags(tags)
    table_data = _load_actions_table(
        db,
        status_filters=status_filters,
        champion_id=champion_id,
        project_id=project_id,
        query=q,
        tags=parsed_tags,
        due_from=from_date,
        due_to=to_date,
        sort=sort,
        page=page,
        page_size=page_size,
    )
    filters = {
        "q": q or "",
        "status": status_filters or [],
        "project_id": project_id,
        "champion_id": champion_id,
        "tags": tags or "",
        "from": from_date.isoformat() if from_date else "",
        "to": to_date.isoformat() if to_date else "",
        "sort": sort or "",
        "page_size": page_size,
    }
    return templates.TemplateResponse(
        "partials/actions_table.html",
        {
            "request": request,
            "actions": table_data["actions"],
            "pagination": table_data,
            "filters": filters,
            "query_builder": build_query_params,
        },
    )


@router.get("/actions/{action_id}", response_class=HTMLResponse, response_model=None)
def action_detail(action_id: int, request: Request, db: Session = Depends(get_db)):
    action = actions_repo.get_action(db, action_id)
    if not action:
        raise HTTPException(status_code=404, detail="Action not found")
    subtasks = actions_repo.list_subtasks(db, action_id)
    days_late = calculate_action_days_late(action, subtasks)
    return templates.TemplateResponse(
        "action_detail.html",
        {
            "request": request,
            "action": action,
            "subtasks": subtasks,
            "days_late": days_late,
            "format_date": format_date,
        },
    )


@router.post("/actions", response_model=None)
def create_action(
    request: Request,
    title: str = Form(...),
    description: str = Form(""),
    project_id: str | None = Form(None),
    champion_id: str | None = Form(None),
    owner: str | None = Form(None),
    status: str = Form("OPEN"),
    due_date: str | None = Form(None),
    tags: str | None = Form(None),
    db: Session = Depends(get_db),
):
    parsed_champion_id = _parse_optional_int(champion_id)
    enforce_action_create_permission(_current_user(request), parsed_champion_id)
    action = Action(
        title=title,
        description=description or "",
        project_id=_parse_optional_int(project_id),
        champion_id=parsed_champion_id,
        owner=owner or None,
        status=status or "OPEN",
        due_date=_parse_optional_date(due_date),
        tags=_parse_tags(tags) or [],
        created_at=datetime.utcnow(),
    )
    action = actions_repo.create_action(db, action)
    return RedirectResponse(url=f"/ui/actions/{action.id}", status_code=303)


@router.post("/actions/{action_id}/delete", response_model=None)
def delete_action(action_id: int, request: Request, db: Session = Depends(get_db)):
    action = actions_repo.get_action(db, action_id)
    if not action:
        raise HTTPException(status_code=404, detail="Action not found")
    user = _current_user(request)
    enforce_write_access(user)
    enforce_action_ownership(user, action)
    actions_repo.delete_action(db, action)
    return RedirectResponse(url="/ui/actions?deleted=1", status_code=303)


@router.post("/actions/{action_id}/subtasks", response_model=None)
def create_subtask(
    action_id: int,
    request: Request,
    title: str = Form(...),
    due_date: str | None = Form(None),
    db: Session = Depends(get_db),
):
    action = actions_repo.get_action(db, action_id)
    if not action:
        raise HTTPException(status_code=404, detail="Action not found")
    user = _current_user(request)
    enforce_write_access(user)
    enforce_action_ownership(user, action)
    subtask = Subtask(
        action_id=action_id,
        title=title,
        status="OPEN",
        due_date=_parse_optional_date(due_date),
        created_at=datetime.utcnow(),
    )
    actions_repo.create_subtask(db, subtask)
    subtasks = actions_repo.list_subtasks(db, action_id)
    if request.headers.get("HX-Request"):
        return _render_subtasks(request, action, subtasks)
    return RedirectResponse(url=f"/ui/actions/{action_id}", status_code=303)


@router.patch("/actions/{action_id}/subtasks/{subtask_id}", response_model=None)
def update_subtask(
    action_id: int,
    subtask_id: int,
    request: Request,
    title: str | None = Form(None),
    status: str | None = Form(None),
    due_date: str | None = Form(None),
    close: str | None = Form(None),
    db: Session = Depends(get_db),
):
    action = actions_repo.get_action(db, action_id)
    if not action:
        raise HTTPException(status_code=404, detail="Action not found")
    subtask = actions_repo.get_subtask(db, subtask_id)
    if not subtask:
        raise HTTPException(status_code=404, detail="Subtask not found")
    user = _current_user(request)
    enforce_write_access(user)
    enforce_action_ownership(user, action)

    if title is not None:
        subtask.title = title
    if due_date is not None:
        subtask.due_date = _parse_optional_date(due_date)
    if close:
        subtask.status = "CLOSED"
        subtask.closed_at = datetime.utcnow()
    elif status is not None:
        subtask.status = status
        if status.upper() == "CLOSED" and subtask.closed_at is None:
            subtask.closed_at = datetime.utcnow()
        if status.upper() != "CLOSED":
            subtask.closed_at = None

    actions_repo.update_subtask(db, subtask)
    subtasks = actions_repo.list_subtasks(db, action_id)
    if request.headers.get("HX-Request"):
        return _render_subtasks(request, action, subtasks)
    return RedirectResponse(url=f"/ui/actions/{action_id}", status_code=303)


@router.post("/actions/{action_id}/subtasks/{subtask_id}/delete", response_model=None)
def delete_subtask(
    action_id: int,
    subtask_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    action = actions_repo.get_action(db, action_id)
    if not action:
        raise HTTPException(status_code=404, detail="Action not found")
    subtask = actions_repo.get_subtask(db, subtask_id)
    if not subtask:
        raise HTTPException(status_code=404, detail="Subtask not found")
    user = _current_user(request)
    enforce_write_access(user)
    enforce_action_ownership(user, action)
    actions_repo.delete_subtask(db, subtask)
    subtasks = actions_repo.list_subtasks(db, action_id)
    if request.headers.get("HX-Request"):
        return _render_subtasks(request, action, subtasks)
    return RedirectResponse(url=f"/ui/actions/{action_id}", status_code=303)
