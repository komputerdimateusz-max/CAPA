from __future__ import annotations

from datetime import date
from pathlib import Path

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.core.auth import enforce_admin
from app.db.session import get_db
from app.repositories import champions as champions_repo
from app.repositories import projects as projects_repo
from app.models.user import User
from app.services import settings as settings_service
from app.services import users as users_service
from app.ui.utils import format_date

router = APIRouter(prefix="/ui", tags=["ui"])

TEMPLATES_DIR = Path(__file__).resolve().parents[1] / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


def _parse_optional_date(value: str | None) -> date | None:
    if not value:
        return None
    return date.fromisoformat(value)


def _parse_optional_int(value: str | None, label: str) -> int | None:
    if value is None:
        return None
    cleaned = value.strip()
    if not cleaned:
        return None
    try:
        return int(cleaned)
    except ValueError as exc:
        raise ValueError(f"{label} must be an integer.") from exc


def _parse_optional_float(value: str | None, label: str) -> float | None:
    if value is None:
        return None
    cleaned = value.strip()
    if not cleaned:
        return None
    try:
        return float(cleaned)
    except ValueError as exc:
        raise ValueError(f"{label} must be a number.") from exc


def _current_user(request: Request):
    return getattr(request.state, "user", None)


def _render_settings(
    request: Request,
    db: Session,
    champion_id: int | None,
    project_id: int | None,
    message: str | None = None,
    error: str | None = None,
    form: dict[str, str] | None = None,
    open_modal: str | None = None,
):
    champions = champions_repo.list_champions(db)
    projects = projects_repo.list_projects(db)
    users = users_service.list_users(db)
    selected_champion = champions_repo.get_champion(db, champion_id) if champion_id else None
    selected_project = projects_repo.get_project(db, project_id) if project_id else None
    return templates.TemplateResponse(
        "settings.html",
        {
            "request": request,
            "champions": champions,
            "projects": projects,
            "users": users,
            "selected_champion": selected_champion,
            "selected_project": selected_project,
            "message": message,
            "error": error,
            "form": form or {},
            "format_date": format_date,
            "open_modal": open_modal,
            "project_status_options": settings_service.ALLOWED_PROJECT_STATUSES,
            "user_role_options": users_service.ALLOWED_USER_ROLES,
        },
    )


@router.get("/settings", response_class=HTMLResponse, response_model=None)
def settings_page(
    request: Request,
    champion_id: int | None = None,
    project_id: int | None = None,
    message: str | None = None,
    created: str | None = None,
    error: str | None = None,
    db: Session = Depends(get_db),
):
    created_message = {
        "champion": "Champion added",
        "project": "Project added",
    }.get((created or "").strip().lower())
    return _render_settings(
        request,
        db,
        champion_id=champion_id,
        project_id=project_id,
        message=message or created_message,
        error=error,
    )


@router.get("/settings/users", response_model=None)
def list_users(db: Session = Depends(get_db)):
    users = users_service.list_users(db)
    return [
        {"id": user.id, "email": user.email, "role": user.role, "created_at": user.created_at}
        for user in users
    ]


@router.post("/settings/users/{user_id}/role", response_model=None)
def update_user_role(
    user_id: int,
    request: Request,
    role: str = Form(...),
    db: Session = Depends(get_db),
):
    # temporary policy: any authenticated user can update any user's role
    try:
        user = db.get(User, user_id)
        if user is None:
            raise ValueError("User not found.")
        users_service.upsert_user_role(db, user_id=user_id, email=user.email, role=role)
    except ValueError as exc:
        return _render_settings(
            request,
            db,
            champion_id=None,
            project_id=None,
            error=str(exc),
        )
    return RedirectResponse(
        url="/ui/settings?message=User+role+updated",
        status_code=303,
    )


@router.post("/settings/champions", response_model=None)
def add_champion(
    request: Request,
    first_name: str = Form(...),
    last_name: str = Form(...),
    email: str | None = Form(default=None),
    position: str | None = Form(default=None),
    birth_date: str | None = Form(default=None),
    db: Session = Depends(get_db),
):
    enforce_admin(_current_user(request))
    try:
        champion = settings_service.create_champion(
            db,
            first_name=first_name,
            last_name=last_name,
            email=email,
            position=position,
            birth_date=_parse_optional_date(birth_date),
        )
    except ValueError as exc:
        return _render_settings(
            request,
            db,
            champion_id=None,
            project_id=None,
            error=str(exc),
            form={
                "champion_first_name": first_name,
                "champion_last_name": last_name,
                "champion_email": email or "",
                "champion_position": position or "",
                "champion_birth_date": birth_date or "",
            },
            open_modal="champion",
        )
    return RedirectResponse(
        url=f"/ui/settings?created=champion&champion_id={champion.id}",
        status_code=303,
    )


@router.post("/settings/champions/{champion_id}", response_model=None)
def update_champion(
    champion_id: int,
    request: Request,
    first_name: str = Form(...),
    last_name: str = Form(...),
    email: str | None = Form(default=None),
    position: str | None = Form(default=None),
    birth_date: str | None = Form(default=None),
    db: Session = Depends(get_db),
):
    enforce_admin(_current_user(request))
    try:
        champion = settings_service.update_champion(
            db,
            champion_id,
            first_name=first_name,
            last_name=last_name,
            email=email,
            position=position,
            birth_date=_parse_optional_date(birth_date),
        )
    except ValueError as exc:
        return _render_settings(
            request,
            db,
            champion_id=champion_id,
            project_id=None,
            error=str(exc),
            form={
                "champion_first_name": first_name,
                "champion_last_name": last_name,
                "champion_email": email or "",
                "champion_position": position or "",
                "champion_birth_date": birth_date or "",
            },
        )
    return RedirectResponse(
        url=f"/ui/settings?message=Champion+updated&champion_id={champion.id}",
        status_code=303,
    )


@router.post("/settings/projects", response_model=None)
def add_project(
    request: Request,
    name: str = Form(...),
    status: str | None = Form(default=None),
    max_volume: str | None = Form(default=None),
    flex_percent: str | None = Form(default=None),
    process_engineer_id: str | None = Form(default=None),
    due_date: str | None = Form(default=None),
    db: Session = Depends(get_db),
):
    enforce_admin(_current_user(request))
    try:
        project = settings_service.create_project(
            db,
            name,
            status,
            _parse_optional_int(max_volume, "Max Volume [parts/year]"),
            _parse_optional_float(flex_percent, "Flex [%]"),
            _parse_optional_int(process_engineer_id, "Process Engineer"),
            _parse_optional_date(due_date),
        )
    except ValueError as exc:
        return _render_settings(
            request,
            db,
            champion_id=None,
            project_id=None,
            error=str(exc),
            form={
                "project_name": name,
                "project_status": status or "",
                "project_max_volume": max_volume or "",
                "project_flex_percent": flex_percent or "",
                "project_process_engineer_id": process_engineer_id or "",
                "project_due_date": due_date or "",
            },
            open_modal="project",
        )
    return RedirectResponse(
        url=f"/ui/settings?created=project&project_id={project.id}",
        status_code=303,
    )


@router.post("/settings/projects/{project_id}", response_model=None)
def update_project(
    project_id: int,
    request: Request,
    name: str = Form(...),
    status: str | None = Form(default=None),
    max_volume: str | None = Form(default=None),
    flex_percent: str | None = Form(default=None),
    process_engineer_id: str | None = Form(default=None),
    due_date: str | None = Form(default=None),
    db: Session = Depends(get_db),
):
    enforce_admin(_current_user(request))
    try:
        project = settings_service.update_project(
            db,
            project_id,
            name,
            status,
            _parse_optional_int(max_volume, "Max Volume [parts/year]"),
            _parse_optional_float(flex_percent, "Flex [%]"),
            _parse_optional_int(process_engineer_id, "Process Engineer"),
            _parse_optional_date(due_date),
        )
    except ValueError as exc:
        return _render_settings(
            request,
            db,
            champion_id=None,
            project_id=project_id,
            error=str(exc),
            form={
                "project_name": name,
                "project_status": status or "",
                "project_max_volume": max_volume or "",
                "project_flex_percent": flex_percent or "",
                "project_process_engineer_id": process_engineer_id or "",
                "project_due_date": due_date or "",
            },
        )
    return RedirectResponse(
        url=f"/ui/settings?message=Project+updated&project_id={project.id}",
        status_code=303,
    )
