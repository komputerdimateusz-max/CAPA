from __future__ import annotations

from datetime import date, datetime
import logging
from pathlib import Path
from fastapi import APIRouter, Depends, Form, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.core.auth import (
    enforce_action_create_permission,
    enforce_action_ownership,
    enforce_write_access,
)
from app.core.config import settings
from app.db.session import get_db
from app.models.action import ALLOWED_PROCESS_TYPES, Action
from app.models.subtask import Subtask
from app.repositories import actions as actions_repo
from app.repositories import champions as champions_repo
from app.repositories import projects as projects_repo
from app.repositories import tags as tags_repo
from app.services.kpi import build_actions_kpi
from app.services.metrics import calculate_action_days_late
from app.ui.utils import build_action_rows, build_query_params, format_date

router = APIRouter(prefix="/ui", tags=["ui"])

TEMPLATES_DIR = Path(__file__).resolve().parents[1] / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))
MAX_KPI_ACTIONS = 10000
SORT_OPTIONS = (
    ("created_at_desc", "Created (newest first)"),
    ("created_at_asc", "Created (oldest first)"),
    ("due_date_asc", "Due date (oldest first)"),
    ("due_date_desc", "Due date (newest first)"),
    ("days_late_desc", "Days late (most first)"),
    ("title_asc", "Title (A-Z)"),
)
STATUS_OPTIONS = ("OPEN", "IN_PROGRESS", "BLOCKED", "CLOSED")
PRIORITY_OPTIONS = ("LOW", "MEDIUM", "HIGH", "CRITICAL")
logger = logging.getLogger("app.ui")


PROCESS_LABELS = {
    "moulding": "Moulding",
    "metalization": "Metalization",
    "assembly": "Assembly",
}


def _validate_process_type_or_422(process_type: str | None) -> str:
    normalized = (process_type or "").strip().lower()
    if normalized not in ALLOWED_PROCESS_TYPES:
        raise HTTPException(
            status_code=422,
            detail="Process is required and must be moulding, metalization, or assembly",
        )
    return normalized


def _clear_non_matching_components(action: Action) -> None:
    if action.process_type == "moulding":
        action.metalization_masks = []
        action.assembly_references = []
    elif action.process_type == "metalization":
        action.moulding_tools = []
        action.assembly_references = []
    elif action.process_type == "assembly":
        action.moulding_tools = []
        action.metalization_masks = []


def _action_process_components_label(action: Action) -> str:
    if action.process_type == "moulding":
        return f"Moulding ({len(action.moulding_tools)})"
    if action.process_type == "metalization":
        return f"Metalization ({len(action.metalization_masks)})"
    if action.process_type == "assembly":
        return f"Assembly ({len(action.assembly_references)})"
    return "—"


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
    normalized_sort = actions_repo.normalize_sort(sort)
    actions, total = actions_repo.list_actions(
        db,
        statuses=status_filters,
        champion_id=champion_id,
        project_id=project_id,
        query=query,
        tags=tags,
        due_from=due_from,
        due_to=due_to,
        sort=normalized_sort,
        limit=page_size,
        offset=(page - 1) * page_size,
    )
    subtasks = actions_repo.list_subtasks_for_actions(db, [action.id for action in actions])
    page_rows = build_action_rows(actions, subtasks)

    if settings.dev_mode:
        logger.info("UI actions sort applied: %s", normalized_sort)

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
    tags: list[str] | None = Query(default=None),
    from_date: date | None = Query(default=None, alias="from"),
    to_date: date | None = Query(default=None, alias="to"),
    sort: str | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=200),
    db: Session = Depends(get_db),
):
    table_data = _load_actions_table(
        db,
        status_filters=status_filters,
        champion_id=champion_id,
        project_id=project_id,
        query=q,
        tags=tags,
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
        tags=tags,
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
        "tags": tags or [],
        "from": from_date.isoformat() if from_date else "",
        "to": to_date.isoformat() if to_date else "",
        "sort": actions_repo.normalize_sort(sort),
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
            "all_tags": tags_repo.list_tags(db),
            "pagination": table_data,
            "query_builder": build_query_params,
            "dev_mode": settings.dev_mode,
        },
    )


@router.get("/actions/_table", response_class=HTMLResponse, response_model=None)
def actions_table(
    request: Request,
    status_filters: list[str] | None = Query(default=None, alias="status"),
    champion_id: int | None = None,
    project_id: int | None = None,
    q: str | None = None,
    tags: list[str] | None = Query(default=None),
    from_date: date | None = Query(default=None, alias="from"),
    to_date: date | None = Query(default=None, alias="to"),
    sort: str | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=200),
    db: Session = Depends(get_db),
):
    table_data = _load_actions_table(
        db,
        status_filters=status_filters,
        champion_id=champion_id,
        project_id=project_id,
        query=q,
        tags=tags,
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
        "tags": tags or [],
        "from": from_date.isoformat() if from_date else "",
        "to": to_date.isoformat() if to_date else "",
        "sort": actions_repo.normalize_sort(sort),
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
def action_detail(
    action_id: int,
    request: Request,
    edit: bool = False,
    db: Session = Depends(get_db),
):
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
            "all_tags": tags_repo.list_tags(db),
            "projects": projects_repo.list_projects(db),
            "champions": champions_repo.list_champions(
                db, include_ids=[action.champion_id] if action.champion_id else None
            ),
            "status_options": STATUS_OPTIONS,
            "priority_options": PRIORITY_OPTIONS,
            "edit_mode": edit,
            "process_options": ALLOWED_PROCESS_TYPES,
            "process_labels": PROCESS_LABELS,
            "moulding_tools": actions_repo.list_moulding_tools(db),
            "metalization_masks": actions_repo.list_metalization_masks(db),
            "assembly_references": actions_repo.list_assembly_references(db),
        },
    )


@router.post("/actions/{action_id}/edit", response_model=None)
def update_action_detail(
    action_id: int,
    request: Request,
    title: str = Form(...),
    description: str = Form(""),
    status: str = Form("OPEN"),
    champion_id: str | None = Form(None),
    owner: str | None = Form(None),
    due_date: str | None = Form(None),
    project_id: str | None = Form(None),
    priority: str | None = Form(None),
    process_type: str = Form(...),
    db: Session = Depends(get_db),
):
    action = actions_repo.get_action(db, action_id)
    if not action:
        raise HTTPException(status_code=404, detail="Action not found")
    user = _current_user(request)
    enforce_write_access(user)
    enforce_action_ownership(user, action)

    normalized_status = (status or "OPEN").upper()
    action.title = title
    action.description = description or ""
    action.status = normalized_status
    action.champion_id = _parse_optional_int(champion_id)
    action.owner = owner or None
    action.due_date = _parse_optional_date(due_date)
    action.project_id = _parse_optional_int(project_id)
    action.priority = (priority or "").strip() or None
    previous_process_type = action.process_type
    action.process_type = _validate_process_type_or_422(process_type)
    if action.process_type != previous_process_type:
        _clear_non_matching_components(action)

    if normalized_status == "CLOSED" and action.closed_at is None:
        action.closed_at = datetime.utcnow()
    if normalized_status != "CLOSED":
        action.closed_at = None

    actions_repo.update_action(db, action)
    return RedirectResponse(url=f"/ui/actions/{action_id}", status_code=303)


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
    process_type: str = Form(...),
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
        created_at=datetime.utcnow(),
        process_type=_validate_process_type_or_422(process_type),
    )
    if tags:
        parsed_tags = [item.strip() for item in tags.split(",") if item.strip()]
        action.tags = [tags_repo.get_or_create_tag(db, tag_name) for tag_name in parsed_tags]
    _clear_non_matching_components(action)
    action = actions_repo.create_action(db, action)
    return RedirectResponse(url=f"/ui/actions/{action.id}?edit=1", status_code=303)


@router.post("/actions/{action_id}/moulding-tools/add", response_model=None)
def add_action_moulding_tool(
    action_id: int,
    request: Request,
    tool_id: str | None = Form(None),
    tool_pn: str | None = Form(None),
    db: Session = Depends(get_db),
):
    action = actions_repo.get_action(db, action_id)
    if not action:
        raise HTTPException(status_code=404, detail="Action not found")
    user = _current_user(request)
    enforce_write_access(user)
    enforce_action_ownership(user, action)
    if action.process_type != "moulding":
        raise HTTPException(status_code=400, detail="Action process_type must be moulding")
    tool = actions_repo.get_moulding_tool_by_id(db, int(tool_id)) if tool_id else None
    if tool is None and tool_pn:
        tool = actions_repo.get_moulding_tool_by_pn(db, tool_pn.strip())
    if not tool:
        raise HTTPException(status_code=404, detail="Moulding tool not found")
    if all(existing.id != tool.id for existing in action.moulding_tools):
        action.moulding_tools.append(tool)
    actions_repo.update_action(db, action)
    return RedirectResponse(url=f"/ui/actions/{action_id}?edit=1", status_code=303)


@router.post("/actions/{action_id}/moulding-tools/remove", response_model=None)
def remove_action_moulding_tool(
    action_id: int,
    request: Request,
    tool_id: int = Form(...),
    db: Session = Depends(get_db),
):
    action = actions_repo.get_action(db, action_id)
    if not action:
        raise HTTPException(status_code=404, detail="Action not found")
    user = _current_user(request)
    enforce_write_access(user)
    enforce_action_ownership(user, action)
    action.moulding_tools = [tool for tool in action.moulding_tools if tool.id != tool_id]
    actions_repo.update_action(db, action)
    return RedirectResponse(url=f"/ui/actions/{action_id}?edit=1", status_code=303)


@router.post("/actions/{action_id}/metalization-masks/add", response_model=None)
def add_action_metalization_mask(
    action_id: int,
    request: Request,
    mask_id: str | None = Form(None),
    mask_pn: str | None = Form(None),
    db: Session = Depends(get_db),
):
    action = actions_repo.get_action(db, action_id)
    if not action:
        raise HTTPException(status_code=404, detail="Action not found")
    user = _current_user(request)
    enforce_write_access(user)
    enforce_action_ownership(user, action)
    if action.process_type != "metalization":
        raise HTTPException(status_code=400, detail="Action process_type must be metalization")
    mask = actions_repo.get_metalization_mask_by_id(db, int(mask_id)) if mask_id else None
    if mask is None and mask_pn:
        mask = actions_repo.get_metalization_mask_by_pn(db, mask_pn.strip())
    if not mask:
        raise HTTPException(status_code=404, detail="Metalization mask not found")
    if all(existing.id != mask.id for existing in action.metalization_masks):
        action.metalization_masks.append(mask)
    actions_repo.update_action(db, action)
    return RedirectResponse(url=f"/ui/actions/{action_id}?edit=1", status_code=303)


@router.post("/actions/{action_id}/metalization-masks/remove", response_model=None)
def remove_action_metalization_mask(
    action_id: int,
    request: Request,
    mask_id: int = Form(...),
    db: Session = Depends(get_db),
):
    action = actions_repo.get_action(db, action_id)
    if not action:
        raise HTTPException(status_code=404, detail="Action not found")
    user = _current_user(request)
    enforce_write_access(user)
    enforce_action_ownership(user, action)
    action.metalization_masks = [mask for mask in action.metalization_masks if mask.id != mask_id]
    actions_repo.update_action(db, action)
    return RedirectResponse(url=f"/ui/actions/{action_id}?edit=1", status_code=303)


@router.post("/actions/{action_id}/assembly-references/add", response_model=None)
def add_action_assembly_reference(
    action_id: int,
    request: Request,
    reference_id: str | None = Form(None),
    reference_name: str | None = Form(None),
    db: Session = Depends(get_db),
):
    action = actions_repo.get_action(db, action_id)
    if not action:
        raise HTTPException(status_code=404, detail="Action not found")
    user = _current_user(request)
    enforce_write_access(user)
    enforce_action_ownership(user, action)
    if action.process_type != "assembly":
        raise HTTPException(status_code=400, detail="Action process_type must be assembly")
    reference = (
        actions_repo.get_assembly_reference_by_id(db, int(reference_id)) if reference_id else None
    )
    if reference is None and reference_name:
        reference = actions_repo.get_assembly_reference_by_name(db, reference_name.strip())
    if not reference:
        raise HTTPException(status_code=404, detail="Assembly reference not found")
    if all(existing.id != reference.id for existing in action.assembly_references):
        action.assembly_references.append(reference)
    actions_repo.update_action(db, action)
    return RedirectResponse(url=f"/ui/actions/{action_id}?edit=1", status_code=303)


@router.post("/actions/{action_id}/assembly-references/remove", response_model=None)
def remove_action_assembly_reference(
    action_id: int,
    request: Request,
    reference_id: int = Form(...),
    db: Session = Depends(get_db),
):
    action = actions_repo.get_action(db, action_id)
    if not action:
        raise HTTPException(status_code=404, detail="Action not found")
    user = _current_user(request)
    enforce_write_access(user)
    enforce_action_ownership(user, action)
    action.assembly_references = [
        reference for reference in action.assembly_references if reference.id != reference_id
    ]
    actions_repo.update_action(db, action)
    return RedirectResponse(url=f"/ui/actions/{action_id}?edit=1", status_code=303)


@router.post("/actions/{action_id}/tags", response_model=None)
def add_action_tag(
    action_id: int,
    request: Request,
    tag_name: str = Form(...),
    db: Session = Depends(get_db),
):
    action = actions_repo.get_action(db, action_id)
    if not action:
        raise HTTPException(status_code=404, detail="Action not found")
    user = _current_user(request)
    enforce_write_access(user)
    enforce_action_ownership(user, action)
    tag = tags_repo.get_or_create_tag(db, tag_name)
    if tag not in action.tags:
        action.tags.append(tag)
    actions_repo.update_action(db, action)
    return RedirectResponse(url=f"/ui/actions/{action_id}", status_code=303)


@router.post("/actions/{action_id}/tags/{tag_id}/delete", response_model=None)
def remove_action_tag(
    action_id: int,
    tag_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    action = actions_repo.get_action(db, action_id)
    if not action:
        raise HTTPException(status_code=404, detail="Action not found")
    user = _current_user(request)
    enforce_write_access(user)
    enforce_action_ownership(user, action)
    action.tags = [tag for tag in action.tags if tag.id != tag_id]
    actions_repo.update_action(db, action)
    return RedirectResponse(url=f"/ui/actions/{action_id}", status_code=303)


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
        process_type=_validate_process_type_or_422(process_type),
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
