from __future__ import annotations

from datetime import date
from pathlib import Path

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.repositories import champions as champions_repo
from app.repositories import projects as projects_repo
from app.services import settings as settings_service
from app.ui.utils import format_date

router = APIRouter(prefix="/ui", tags=["ui"])

TEMPLATES_DIR = Path(__file__).resolve().parents[1] / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


def _parse_optional_date(value: str | None) -> date | None:
    if not value:
        return None
    return date.fromisoformat(value)


def _render_settings(
    request: Request,
    db: Session,
    champion_id: int | None,
    project_id: int | None,
    message: str | None = None,
    error: str | None = None,
    form: dict[str, str] | None = None,
):
    champions = champions_repo.list_champions(db)
    projects = projects_repo.list_projects(db)
    selected_champion = champions_repo.get_champion(db, champion_id) if champion_id else None
    selected_project = projects_repo.get_project(db, project_id) if project_id else None
    return templates.TemplateResponse(
        "settings.html",
        {
            "request": request,
            "champions": champions,
            "projects": projects,
            "selected_champion": selected_champion,
            "selected_project": selected_project,
            "message": message,
            "error": error,
            "form": form or {},
            "format_date": format_date,
        },
    )


@router.get("/settings", response_class=HTMLResponse, response_model=None)
def settings_page(
    request: Request,
    champion_id: int | None = None,
    project_id: int | None = None,
    message: str | None = None,
    error: str | None = None,
    db: Session = Depends(get_db),
):
    return _render_settings(
        request,
        db,
        champion_id=champion_id,
        project_id=project_id,
        message=message,
        error=error,
    )


@router.post("/settings/champions", response_model=None)
def add_champion(
    request: Request,
    name: str = Form(...),
    db: Session = Depends(get_db),
):
    try:
        champion = settings_service.create_champion(db, name)
    except ValueError as exc:
        return _render_settings(
            request,
            db,
            champion_id=None,
            project_id=None,
            error=str(exc),
            form={"champion_name": name},
        )
    return RedirectResponse(
        url=f"/ui/settings?message=Champion+added&champion_id={champion.id}",
        status_code=303,
    )


@router.post("/settings/champions/{champion_id}", response_model=None)
def update_champion(
    champion_id: int,
    request: Request,
    name: str = Form(...),
    db: Session = Depends(get_db),
):
    try:
        champion = settings_service.update_champion(db, champion_id, name)
    except ValueError as exc:
        return _render_settings(
            request,
            db,
            champion_id=champion_id,
            project_id=None,
            error=str(exc),
            form={"champion_name": name},
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
    due_date: str | None = Form(default=None),
    db: Session = Depends(get_db),
):
    try:
        project = settings_service.create_project(db, name, status, _parse_optional_date(due_date))
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
                "project_due_date": due_date or "",
            },
        )
    return RedirectResponse(
        url=f"/ui/settings?message=Project+added&project_id={project.id}",
        status_code=303,
    )


@router.post("/settings/projects/{project_id}", response_model=None)
def update_project(
    project_id: int,
    request: Request,
    name: str = Form(...),
    status: str | None = Form(default=None),
    due_date: str | None = Form(default=None),
    db: Session = Depends(get_db),
):
    try:
        project = settings_service.update_project(db, project_id, name, status, _parse_optional_date(due_date))
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
                "project_due_date": due_date or "",
            },
        )
    return RedirectResponse(
        url=f"/ui/settings?message=Project+updated&project_id={project.id}",
        status_code=303,
    )
