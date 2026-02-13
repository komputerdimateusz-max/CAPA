from __future__ import annotations

from datetime import date
from pathlib import Path
from urllib.parse import quote_plus

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.core.auth import enforce_admin
from app.db.session import get_db
from app.models.user import User
from app.repositories import champions as champions_repo
from app.repositories import projects as projects_repo
from app.schemas.assembly_line import AssemblyLineCreate, AssemblyLineUpdate
from app.schemas.metalization import (
    MetalizationChamberCreate,
    MetalizationChamberUpdate,
    MetalizationMaskCreate,
    MetalizationMaskUpdate,
)
from app.schemas.moulding import MouldingMachineCreate, MouldingMachineUpdate, MouldingToolCreate, MouldingToolUpdate
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


def _parse_int_list(values: list[str] | None, label: str) -> list[int]:
    if not values:
        return []
    parsed: list[int] = []
    for value in values:
        cleaned = value.strip()
        if not cleaned:
            continue
        try:
            parsed.append(int(cleaned))
        except ValueError as exc:
            raise ValueError(f"{label} must contain integers only.") from exc
    return parsed


def _current_user(request: Request):
    return getattr(request.state, "user", None)


def _resolve_tool_id(db: Session, value: str) -> int:
    cleaned = value.strip()
    if not cleaned:
        raise ValueError("Moulding tool is required.")
    for tool in settings_service.list_moulding_tools(db):
        if tool.tool_pn.lower() == cleaned.lower():
            return tool.id
    parsed = _parse_optional_int(value, "Moulding tool")
    if parsed is not None:
        return parsed
    raise ValueError("Selected moulding tool does not exist.")




def _resolve_mask_id(db: Session, value: str) -> int:
    cleaned = value.strip()
    if not cleaned:
        raise ValueError("Metalization mask is required.")
    for mask in settings_service.list_metalization_masks(db):
        if mask.mask_pn.lower() == cleaned.lower():
            return mask.id
    parsed = _parse_optional_int(value, "Metalization mask")
    if parsed is not None:
        return parsed
    raise ValueError("Selected metalization mask does not exist.")


def _resolve_line_id(db: Session, value: str, *, from_line_number: bool = False) -> int:
    cleaned = value.strip()
    if not cleaned:
        if from_line_number:
            raise ValueError("Line number is required.")
        raise ValueError("Assembly line is required.")
    for line in settings_service.list_assembly_lines(db):
        if line.line_number.lower() == cleaned.lower():
            return line.id
    parsed = _parse_optional_int(value, "Assembly line")
    if parsed is not None and not from_line_number:
        return parsed
    if from_line_number:
        raise ValueError("Unknown line number")
    raise ValueError("Selected assembly line does not exist.")


def _base_settings_context(db: Session) -> dict[str, object]:
    champions = champions_repo.list_champions(db)
    projects = projects_repo.list_projects(db)
    users = users_service.list_users(db)
    moulding_tools = settings_service.list_moulding_tools(db)
    moulding_machines = settings_service.list_moulding_machines(db)
    assembly_lines = settings_service.list_assembly_lines(db)
    metalization_masks = settings_service.list_metalization_masks(db)
    metalization_chambers = settings_service.list_metalization_chambers(db)
    return {
        "champions": champions,
        "projects": projects,
        "users": users,
        "moulding_tools": moulding_tools,
        "moulding_machines": moulding_machines,
        "assembly_lines": assembly_lines,
        "metalization_masks": metalization_masks,
        "metalization_chambers": metalization_chambers,
        "project_status_options": settings_service.ALLOWED_PROJECT_STATUSES,
        "user_role_options": users_service.ALLOWED_USER_ROLES,
    }


def _render_settings(
    template_name: str,
    request: Request,
    db: Session,
    champion_id: int | None,
    project_id: int | None,
    tool_id: int | None = None,
    machine_id: int | None = None,
    message: str | None = None,
    error: str | None = None,
    form: dict[str, str] | None = None,
    open_modal: str | None = None,
    assembly_line_id: int | None = None,
    mask_id: int | None = None,
    chamber_id: int | None = None,
):
    context = _base_settings_context(db)
    champions = context["champions"]
    projects = context["projects"]
    moulding_tools = context["moulding_tools"]
    moulding_machines = context["moulding_machines"]
    selected_champion = champions_repo.get_champion(db, champion_id) if champion_id else None
    selected_project = projects_repo.get_project(db, project_id) if project_id else None
    selected_moulding_tool = next((tool for tool in moulding_tools if tool.id == tool_id), None) if tool_id else None
    selected_moulding_machine = (
        next((machine for machine in moulding_machines if machine.id == machine_id), None) if machine_id else None
    )
    assembly_lines = context["assembly_lines"]
    selected_assembly_line = next((line for line in assembly_lines if line.id == assembly_line_id), None) if assembly_line_id else None
    metalization_masks = context["metalization_masks"]
    selected_metalization_mask = next((mask for mask in metalization_masks if mask.id == mask_id), None) if mask_id else None
    metalization_chambers = context["metalization_chambers"]
    selected_metalization_chamber = (
        next((chamber for chamber in metalization_chambers if chamber.id == chamber_id), None) if chamber_id else None
    )
    return templates.TemplateResponse(
        template_name,
        {
            "request": request,
            "selected_champion": selected_champion,
            "selected_project": selected_project,
            "selected_moulding_tool": selected_moulding_tool,
            "selected_moulding_machine": selected_moulding_machine,
            "message": message,
            "error": error,
            "form": form or {},
            "format_date": format_date,
            "open_modal": open_modal,
            "selected_assembly_line": selected_assembly_line,
            "selected_metalization_mask": selected_metalization_mask,
            "selected_metalization_chamber": selected_metalization_chamber,
            **context,
        },
    )


@router.get("/settings", response_class=HTMLResponse, response_model=None)
def settings_page(
    request: Request,
    message: str | None = None,
    error: str | None = None,
    db: Session = Depends(get_db),
):
    return templates.TemplateResponse(
        "settings_home.html",
        {
            "request": request,
            "message": message,
            "error": error,
        },
    )


@router.get("/settings/champions", response_class=HTMLResponse, response_model=None)
def settings_champions_page(
    request: Request,
    champion_id: int | None = None,
    message: str | None = None,
    created: str | None = None,
    error: str | None = None,
    db: Session = Depends(get_db),
):
    return _render_settings(
        "settings_champions.html",
        request,
        db,
        champion_id=champion_id,
        project_id=None,
        message=message or ("Champion added" if (created or "").strip().lower() == "champion" else None),
        error=error,
    )


@router.get("/settings/projects", response_class=HTMLResponse, response_model=None)
def settings_projects_page(
    request: Request,
    project_id: int | None = None,
    message: str | None = None,
    created: str | None = None,
    error: str | None = None,
    db: Session = Depends(get_db),
):
    return _render_settings(
        "settings_projects.html",
        request,
        db,
        champion_id=None,
        project_id=project_id,
        message=message or ("Project added" if (created or "").strip().lower() == "project" else None),
        error=error,
    )


@router.get("/settings/moulding-tools", response_class=HTMLResponse, response_model=None)
def settings_moulding_tools_page(
    request: Request,
    tool_id: int | None = None,
    message: str | None = None,
    created: str | None = None,
    error: str | None = None,
    db: Session = Depends(get_db),
):
    return _render_settings(
        "settings_moulding_tools.html",
        request,
        db,
        champion_id=None,
        project_id=None,
        tool_id=tool_id,
        message=message or ("Moulding tool added" if (created or "").strip().lower() == "moulding_tool" else None),
        error=error,
    )


@router.get("/settings/moulding-machines", response_class=HTMLResponse, response_model=None)
def settings_moulding_machines_page(
    request: Request,
    machine_id: int | None = None,
    message: str | None = None,
    created: str | None = None,
    error: str | None = None,
    db: Session = Depends(get_db),
):
    return _render_settings(
        "settings_moulding_machines.html",
        request,
        db,
        champion_id=None,
        project_id=None,
        machine_id=machine_id,
        message=message
        or ("Moulding machine added" if (created or "").strip().lower() == "moulding_machine" else None),
        error=error,
    )




@router.get("/settings/assembly-lines", response_class=HTMLResponse, response_model=None)
def settings_assembly_lines_page(
    request: Request,
    assembly_line_id: int | None = None,
    message: str | None = None,
    created: str | None = None,
    error: str | None = None,
    db: Session = Depends(get_db),
):
    return _render_settings(
        "settings_assembly_lines.html",
        request,
        db,
        champion_id=None,
        project_id=None,
        message=message or ("Assembly line added" if (created or "").strip().lower() == "assembly_line" else None),
        error=error,
        assembly_line_id=assembly_line_id,
    )

@router.get("/settings/metalization-masks", response_class=HTMLResponse, response_model=None)
def settings_metalization_masks_page(
    request: Request,
    mask_id: int | None = None,
    message: str | None = None,
    created: str | None = None,
    error: str | None = None,
    db: Session = Depends(get_db),
):
    return _render_settings(
        "settings_metalization_masks.html",
        request,
        db,
        champion_id=None,
        project_id=None,
        message=message or ("Metalization mask added" if (created or "").strip().lower() == "metalization_mask" else None),
        error=error,
        mask_id=mask_id,
    )


@router.get("/settings/metalization-chambers", response_class=HTMLResponse, response_model=None)
def settings_metalization_chambers_page(
    request: Request,
    chamber_id: int | None = None,
    message: str | None = None,
    created: str | None = None,
    error: str | None = None,
    db: Session = Depends(get_db),
):
    return _render_settings(
        "settings_metalization_chambers.html",
        request,
        db,
        champion_id=None,
        project_id=None,
        message=message
        or ("Metalization chamber added" if (created or "").strip().lower() == "metalization_chamber" else None),
        error=error,
        chamber_id=chamber_id,
    )


@router.get("/settings/users", response_class=HTMLResponse, response_model=None)
def settings_users_page(
    request: Request,
    message: str | None = None,
    error: str | None = None,
    db: Session = Depends(get_db),
):
    return _render_settings(
        "settings_users.html",
        request,
        db,
        champion_id=None,
        project_id=None,
        message=message,
        error=error,
    )


@router.post("/settings/users/{user_id}/role", response_model=None)
def update_user_role(
    user_id: int,
    request: Request,
    role: str = Form(...),
    db: Session = Depends(get_db),
):
    try:
        user = db.get(User, user_id)
        if user is None:
            raise ValueError("User not found.")
        users_service.upsert_user_role(db, user_id=user_id, email=user.email, role=role)
    except ValueError as exc:
        return _render_settings("settings_users.html", request, db, champion_id=None, project_id=None, error=str(exc))
    return RedirectResponse(url="/ui/settings/users?message=User+role+updated", status_code=303)


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
            "settings_champions.html",
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
    return RedirectResponse(url=f"/ui/settings/champions?created=champion&champion_id={champion.id}", status_code=303)


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
            "settings_champions.html",
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
    return RedirectResponse(url=f"/ui/settings/champions?message=Champion+updated&champion_id={champion.id}", status_code=303)


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
            [],
            [],
        )
    except ValueError as exc:
        return _render_settings(
            "settings_projects.html",
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
    return RedirectResponse(url=f"/ui/settings/projects?created=project&project_id={project.id}", status_code=303)


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
    existing_project = projects_repo.get_project(db, project_id)
    if existing_project is None:
        return _render_settings(
            "settings_projects.html",
            request,
            db,
            champion_id=None,
            project_id=None,
            error="Project not found.",
        )
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
            [tool.id for tool in existing_project.moulding_tools],
            [line.id for line in existing_project.assembly_lines],
        )
    except ValueError as exc:
        return _render_settings(
            "settings_projects.html",
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
    return RedirectResponse(url=f"/ui/settings/projects?message=Project+updated&project_id={project.id}", status_code=303)


@router.post("/settings/projects/{project_id}/tools/add", response_model=None)
def add_project_tool(
    project_id: int,
    request: Request,
    tool_id: str | None = Form(default=None),
    tool_pn: str | None = Form(default=None),
    db: Session = Depends(get_db),
):
    enforce_admin(_current_user(request))
    try:
        tool_value = tool_pn if tool_pn is not None else tool_id
        if tool_value is None:
            raise ValueError("Moulding tool is required.")
        parsed_tool_id = _resolve_tool_id(db, tool_value)
        settings_service.add_project_moulding_tool(db, project_id=project_id, tool_id=parsed_tool_id)
    except ValueError as exc:
        return RedirectResponse(
            url=f"/ui/settings/projects?project_id={project_id}&error={quote_plus(str(exc))}",
            status_code=303,
        )
    return RedirectResponse(
        url=f"/ui/settings/projects?project_id={project_id}&message=Moulding+tool+assigned",
        status_code=303,
    )


@router.post("/settings/projects/{project_id}/tools/remove", response_model=None)
def remove_project_tool(
    project_id: int,
    request: Request,
    tool_id: str = Form(...),
    db: Session = Depends(get_db),
):
    enforce_admin(_current_user(request))
    try:
        parsed_tool_id = _resolve_tool_id(db, tool_id)
        settings_service.remove_project_moulding_tool(db, project_id=project_id, tool_id=parsed_tool_id)
    except ValueError as exc:
        return RedirectResponse(
            url=f"/ui/settings/projects?project_id={project_id}&error={quote_plus(str(exc))}",
            status_code=303,
        )
    return RedirectResponse(
        url=f"/ui/settings/projects?project_id={project_id}&message=Moulding+tool+removed",
        status_code=303,
    )


@router.post("/settings/projects/{project_id}/lines/add", response_model=None)
def add_project_line(
    project_id: int,
    request: Request,
    line_number: str | None = Form(default=None),
    line_id: str | None = Form(default=None),
    db: Session = Depends(get_db),
):
    enforce_admin(_current_user(request))
    try:
        if line_number is not None:
            parsed_line_id = _resolve_line_id(db, line_number, from_line_number=True)
        elif line_id is not None:
            parsed_line_id = _resolve_line_id(db, line_id)
        else:
            raise ValueError("Assembly line is required.")
        settings_service.add_project_assembly_line(db, project_id=project_id, line_id=parsed_line_id)
    except ValueError as exc:
        return RedirectResponse(
            url=f"/ui/settings/projects?project_id={project_id}&error={quote_plus(str(exc))}",
            status_code=303,
        )
    return RedirectResponse(
        url=f"/ui/settings/projects?project_id={project_id}&message=Assembly+line+assigned",
        status_code=303,
    )


@router.post("/settings/projects/{project_id}/lines/remove", response_model=None)
def remove_project_line(
    project_id: int,
    request: Request,
    line_id: str = Form(...),
    db: Session = Depends(get_db),
):
    enforce_admin(_current_user(request))
    try:
        parsed_line_id = _resolve_line_id(db, line_id)
        settings_service.remove_project_assembly_line(db, project_id=project_id, line_id=parsed_line_id)
    except ValueError as exc:
        return RedirectResponse(
            url=f"/ui/settings/projects?project_id={project_id}&error={quote_plus(str(exc))}",
            status_code=303,
        )
    return RedirectResponse(
        url=f"/ui/settings/projects?project_id={project_id}&message=Assembly+line+removed",
        status_code=303,
    )


@router.post("/settings/projects/{project_id}/metalization-masks/add", response_model=None)
def add_project_metalization_mask(
    project_id: int,
    request: Request,
    mask_pn: str = Form(...),
    db: Session = Depends(get_db),
):
    enforce_admin(_current_user(request))
    try:
        parsed_mask_id = _resolve_mask_id(db, mask_pn)
        settings_service.add_project_metalization_mask(db, project_id=project_id, mask_id=parsed_mask_id)
    except ValueError as exc:
        return RedirectResponse(
            url=f"/ui/settings/projects?project_id={project_id}&error={quote_plus(str(exc))}",
            status_code=303,
        )
    return RedirectResponse(
        url=f"/ui/settings/projects?project_id={project_id}&message=Metalization+mask+assigned",
        status_code=303,
    )


@router.post("/settings/projects/{project_id}/metalization-masks/remove", response_model=None)
def remove_project_metalization_mask(
    project_id: int,
    request: Request,
    mask_id: str = Form(...),
    db: Session = Depends(get_db),
):
    enforce_admin(_current_user(request))
    try:
        parsed_mask_id = _resolve_mask_id(db, mask_id)
        settings_service.remove_project_metalization_mask(db, project_id=project_id, mask_id=parsed_mask_id)
    except ValueError as exc:
        return RedirectResponse(
            url=f"/ui/settings/projects?project_id={project_id}&error={quote_plus(str(exc))}",
            status_code=303,
        )
    return RedirectResponse(
        url=f"/ui/settings/projects?project_id={project_id}&message=Metalization+mask+removed",
        status_code=303,
    )


@router.get("/settings/projects/{project_id}/assignments", response_class=HTMLResponse, response_model=None)
def project_assignments_page(
    project_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    project = projects_repo.get_project(db, project_id)
    if project is None:
        return RedirectResponse(url="/ui/settings/projects?error=Project+not+found", status_code=303)
    return templates.TemplateResponse(
        "settings_project_assignments.html",
        {
            "request": request,
            "project": project,
            "format_date": format_date,
        },
    )


@router.post("/settings/moulding-tools", response_model=None)
def add_moulding_tool(
    request: Request,
    tool_pn: str = Form(...),
    description: str | None = Form(default=None),
    ct_seconds: str = Form(...),
    db: Session = Depends(get_db),
):
    enforce_admin(_current_user(request))
    try:
        tool = settings_service.create_moulding_tool(
            db,
            MouldingToolCreate(tool_pn=tool_pn, description=description, ct_seconds=float(ct_seconds)),
        )
    except (ValidationError, ValueError, TypeError) as exc:
        return _render_settings(
            "settings_moulding_tools.html",
            request,
            db,
            champion_id=None,
            project_id=None,
            error=str(exc),
            form={
                "tool_pn": tool_pn,
                "tool_description": description or "",
                "tool_ct_seconds": ct_seconds,
            },
            open_modal="moulding-tool",
        )
    return RedirectResponse(url=f"/ui/settings/moulding-tools?created=moulding_tool&tool_id={tool.id}", status_code=303)


@router.post("/settings/moulding-tools/{tool_id}", response_model=None)
def update_moulding_tool(
    tool_id: int,
    request: Request,
    tool_pn: str = Form(...),
    description: str | None = Form(default=None),
    ct_seconds: str = Form(...),
    db: Session = Depends(get_db),
):
    enforce_admin(_current_user(request))
    try:
        tool = settings_service.update_moulding_tool(
            db,
            tool_id,
            MouldingToolUpdate(tool_pn=tool_pn, description=description, ct_seconds=float(ct_seconds)),
        )
    except (ValidationError, ValueError, TypeError) as exc:
        return _render_settings(
            "settings_moulding_tools.html",
            request,
            db,
            champion_id=None,
            project_id=None,
            tool_id=tool_id,
            error=str(exc),
            form={
                "tool_pn": tool_pn,
                "tool_description": description or "",
                "tool_ct_seconds": ct_seconds,
            },
        )
    return RedirectResponse(url=f"/ui/settings/moulding-tools?message=Moulding+tool+updated&tool_id={tool.id}", status_code=303)


@router.post("/settings/moulding-tools/{tool_id}/delete", response_model=None)
def delete_moulding_tool(tool_id: int, request: Request, db: Session = Depends(get_db)):
    enforce_admin(_current_user(request))
    try:
        settings_service.delete_moulding_tool(db, tool_id)
    except ValueError as exc:
        return _render_settings(
            "settings_moulding_tools.html",
            request,
            db,
            champion_id=None,
            project_id=None,
            error=str(exc),
        )
    return RedirectResponse(url="/ui/settings/moulding-tools?message=Moulding+tool+deleted", status_code=303)


@router.post("/settings/moulding-machines", response_model=None)
def add_moulding_machine(
    request: Request,
    machine_number: str = Form(...),
    tonnage: str | None = Form(default=None),
    tool_ids: list[str] = Form(default=[]),
    db: Session = Depends(get_db),
):
    enforce_admin(_current_user(request))
    try:
        parsed_tonnage = _parse_optional_int(tonnage, "Tonnage")
        machine = settings_service.create_moulding_machine(
            db,
            MouldingMachineCreate(
                machine_number=machine_number,
                tonnage=parsed_tonnage,
                tool_ids=_parse_int_list(tool_ids, "Tools assigned"),
            ),
        )
    except (ValidationError, ValueError) as exc:
        return _render_settings(
            "settings_moulding_machines.html",
            request,
            db,
            champion_id=None,
            project_id=None,
            error=str(exc),
            form={
                "machine_number": machine_number,
                "machine_tonnage": tonnage or "",
                "machine_tool_ids": ",".join(tool_ids),
            },
            open_modal="moulding-machine",
        )
    return RedirectResponse(
        url=f"/ui/settings/moulding-machines?created=moulding_machine&machine_id={machine.id}",
        status_code=303,
    )


@router.post("/settings/moulding-machines/{machine_id}", response_model=None)
def update_moulding_machine(
    machine_id: int,
    request: Request,
    machine_number: str = Form(...),
    tonnage: str | None = Form(default=None),
    tool_ids: list[str] | None = Form(default=None),
    db: Session = Depends(get_db),
):
    enforce_admin(_current_user(request))
    try:
        parsed_tonnage = _parse_optional_int(tonnage, "Tonnage")
        parsed_tool_ids = _parse_int_list(tool_ids, "Tools assigned") if tool_ids is not None else None
        if parsed_tool_ids is None:
            existing_machine = next((m for m in settings_service.list_moulding_machines(db) if m.id == machine_id), None)
            parsed_tool_ids = [tool.id for tool in existing_machine.tools] if existing_machine else []
        machine = settings_service.update_moulding_machine(
            db,
            machine_id,
            MouldingMachineUpdate(
                machine_number=machine_number,
                tonnage=parsed_tonnage,
                tool_ids=parsed_tool_ids,
            ),
        )
    except (ValidationError, ValueError) as exc:
        return _render_settings(
            "settings_moulding_machines.html",
            request,
            db,
            champion_id=None,
            project_id=None,
            machine_id=machine_id,
            error=str(exc),
            form={
                "machine_number": machine_number,
                "machine_tonnage": tonnage or "",
                "machine_tool_ids": ",".join(tool_ids or []),
            },
        )
    return RedirectResponse(
        url=f"/ui/settings/moulding-machines?message=Moulding+machine+updated&machine_id={machine.id}",
        status_code=303,
    )


@router.post("/settings/moulding-machines/{machine_id}/tools/add", response_model=None)
def add_moulding_machine_tool(
    machine_id: int,
    request: Request,
    tool_pn: str | None = Form(default=None),
    tool_id: str | None = Form(default=None),
    db: Session = Depends(get_db),
):
    enforce_admin(_current_user(request))
    try:
        parsed_tool_id = _parse_optional_int(tool_id, "Moulding tool") if tool_id is not None else None
        if not (tool_pn and tool_pn.strip()) and parsed_tool_id is None:
            raise ValueError("Moulding tool is required.")
        settings_service.add_moulding_machine_tool(
            db,
            machine_id,
            tool_id=parsed_tool_id,
            tool_pn=tool_pn,
        )
    except ValueError as exc:
        return _render_settings(
            "settings_moulding_machines.html",
            request,
            db,
            champion_id=None,
            project_id=None,
            machine_id=machine_id,
            error=str(exc),
        )
    return RedirectResponse(url=f"/ui/settings/moulding-machines?machine_id={machine_id}", status_code=303)


@router.post("/settings/moulding-machines/{machine_id}/tools/remove", response_model=None)
def remove_moulding_machine_tool(
    machine_id: int,
    request: Request,
    tool_id: str | None = Form(default=None),
    tool_pn: str | None = Form(default=None),
    db: Session = Depends(get_db),
):
    enforce_admin(_current_user(request))
    try:
        parsed_tool_id = _parse_optional_int(tool_id, "Moulding tool") if tool_id is not None else None
        settings_service.remove_moulding_machine_tool(
            db,
            machine_id,
            tool_id=parsed_tool_id,
            tool_pn=tool_pn,
        )
    except ValueError as exc:
        return _render_settings(
            "settings_moulding_machines.html",
            request,
            db,
            champion_id=None,
            project_id=None,
            machine_id=machine_id,
            error=str(exc),
        )
    return RedirectResponse(url=f"/ui/settings/moulding-machines?machine_id={machine_id}", status_code=303)


@router.post("/settings/moulding-machines/{machine_id}/delete", response_model=None)
def delete_moulding_machine(machine_id: int, request: Request, db: Session = Depends(get_db)):
    enforce_admin(_current_user(request))
    try:
        settings_service.delete_moulding_machine(db, machine_id)
    except ValueError as exc:
        return _render_settings(
            "settings_moulding_machines.html",
            request,
            db,
            champion_id=None,
            project_id=None,
            error=str(exc),
        )
    return RedirectResponse(url="/ui/settings/moulding-machines?message=Moulding+machine+deleted", status_code=303)


@router.post("/settings/assembly-lines", response_model=None)
def add_assembly_line(
    request: Request,
    line_number: str = Form(...),
    ct_seconds: str = Form(...),
    hc: str = Form(...),
    db: Session = Depends(get_db),
):
    enforce_admin(_current_user(request))
    try:
        assembly_line = settings_service.create_assembly_line(
            db,
            AssemblyLineCreate(line_number=line_number, ct_seconds=float(ct_seconds), hc=int(hc)),
        )
    except (ValidationError, ValueError, TypeError) as exc:
        return _render_settings(
            "settings_assembly_lines.html",
            request,
            db,
            champion_id=None,
            project_id=None,
            error=str(exc),
            form={
                "assembly_line_number": line_number,
                "assembly_ct_seconds": ct_seconds,
                "assembly_hc": hc,
            },
            open_modal="assembly-line-add",
        )
    return RedirectResponse(
        url=f"/ui/settings/assembly-lines?created=assembly_line&assembly_line_id={assembly_line.id}",
        status_code=303,
    )


@router.post("/settings/assembly-lines/{assembly_line_id}", response_model=None)
def update_assembly_line(
    assembly_line_id: int,
    request: Request,
    line_number: str = Form(...),
    ct_seconds: str = Form(...),
    hc: str = Form(...),
    db: Session = Depends(get_db),
):
    enforce_admin(_current_user(request))
    try:
        assembly_line = settings_service.update_assembly_line(
            db,
            assembly_line_id,
            AssemblyLineUpdate(line_number=line_number, ct_seconds=float(ct_seconds), hc=int(hc)),
        )
    except (ValidationError, ValueError, TypeError) as exc:
        return _render_settings(
            "settings_assembly_lines.html",
            request,
            db,
            champion_id=None,
            project_id=None,
            assembly_line_id=assembly_line_id,
            error=str(exc),
            form={
                "assembly_line_number": line_number,
                "assembly_ct_seconds": ct_seconds,
                "assembly_hc": hc,
            },
            open_modal="assembly-line-edit",
        )
    return RedirectResponse(
        url=f"/ui/settings/assembly-lines?message=Assembly+line+updated&assembly_line_id={assembly_line.id}",
        status_code=303,
    )


@router.post("/settings/assembly-lines/{assembly_line_id}/delete", response_model=None)
def delete_assembly_line(assembly_line_id: int, request: Request, db: Session = Depends(get_db)):
    enforce_admin(_current_user(request))
    try:
        settings_service.delete_assembly_line(db, assembly_line_id)
    except ValueError as exc:
        return _render_settings(
            "settings_assembly_lines.html",
            request,
            db,
            champion_id=None,
            project_id=None,
            assembly_line_id=assembly_line_id,
            error=str(exc),
            open_modal="assembly-line-edit",
        )
    return RedirectResponse(url="/ui/settings/assembly-lines?message=Assembly+line+deleted", status_code=303)


@router.post("/settings/metalization-masks", response_model=None)
def add_metalization_mask(
    request: Request,
    mask_pn: str = Form(...),
    description: str | None = Form(default=None),
    ct_seconds: str = Form(...),
    db: Session = Depends(get_db),
):
    enforce_admin(_current_user(request))
    try:
        mask = settings_service.create_metalization_mask(
            db,
            MetalizationMaskCreate(mask_pn=mask_pn, description=description, ct_seconds=float(ct_seconds)),
        )
    except (ValidationError, ValueError, TypeError) as exc:
        return _render_settings(
            "settings_metalization_masks.html",
            request,
            db,
            champion_id=None,
            project_id=None,
            error=str(exc),
            form={"mask_pn": mask_pn, "mask_description": description or "", "mask_ct_seconds": ct_seconds},
            open_modal="metalization-mask",
        )
    return RedirectResponse(url=f"/ui/settings/metalization-masks?created=metalization_mask&mask_id={mask.id}", status_code=303)


@router.post("/settings/metalization-masks/{mask_id}", response_model=None)
def update_metalization_mask(
    mask_id: int,
    request: Request,
    mask_pn: str = Form(...),
    description: str | None = Form(default=None),
    ct_seconds: str = Form(...),
    db: Session = Depends(get_db),
):
    enforce_admin(_current_user(request))
    try:
        mask = settings_service.update_metalization_mask(
            db,
            mask_id,
            MetalizationMaskUpdate(mask_pn=mask_pn, description=description, ct_seconds=float(ct_seconds)),
        )
    except (ValidationError, ValueError, TypeError) as exc:
        return _render_settings(
            "settings_metalization_masks.html",
            request,
            db,
            champion_id=None,
            project_id=None,
            mask_id=mask_id,
            error=str(exc),
            form={"mask_pn": mask_pn, "mask_description": description or "", "mask_ct_seconds": ct_seconds},
        )
    return RedirectResponse(url=f"/ui/settings/metalization-masks?message=Metalization+mask+updated&mask_id={mask.id}", status_code=303)


@router.post("/settings/metalization-masks/{mask_id}/delete", response_model=None)
def delete_metalization_mask(mask_id: int, request: Request, db: Session = Depends(get_db)):
    enforce_admin(_current_user(request))
    try:
        settings_service.delete_metalization_mask(db, mask_id)
    except ValueError as exc:
        return _render_settings("settings_metalization_masks.html", request, db, champion_id=None, project_id=None, error=str(exc))
    return RedirectResponse(url="/ui/settings/metalization-masks?message=Metalization+mask+deleted", status_code=303)


@router.post("/settings/metalization-chambers", response_model=None)
def add_metalization_chamber(
    request: Request,
    chamber_number: str = Form(...),
    mask_ids: list[str] = Form(default=[]),
    db: Session = Depends(get_db),
):
    enforce_admin(_current_user(request))
    try:
        chamber = settings_service.create_metalization_chamber(
            db,
            MetalizationChamberCreate(chamber_number=chamber_number, mask_ids=_parse_int_list(mask_ids, "Masks assigned")),
        )
    except (ValidationError, ValueError) as exc:
        return _render_settings(
            "settings_metalization_chambers.html",
            request,
            db,
            champion_id=None,
            project_id=None,
            error=str(exc),
            form={"chamber_number": chamber_number, "chamber_mask_ids": ",".join(mask_ids)},
            open_modal="metalization-chamber",
        )
    return RedirectResponse(url=f"/ui/settings/metalization-chambers?created=metalization_chamber&chamber_id={chamber.id}", status_code=303)


@router.post("/settings/metalization-chambers/{chamber_id}", response_model=None)
def update_metalization_chamber(
    chamber_id: int,
    request: Request,
    chamber_number: str = Form(...),
    mask_ids: list[str] | None = Form(default=None),
    db: Session = Depends(get_db),
):
    enforce_admin(_current_user(request))
    try:
        parsed_mask_ids = _parse_int_list(mask_ids, "Masks assigned") if mask_ids is not None else None
        if parsed_mask_ids is None:
            existing_chamber = next((c for c in settings_service.list_metalization_chambers(db) if c.id == chamber_id), None)
            parsed_mask_ids = [mask.id for mask in existing_chamber.masks] if existing_chamber else []
        chamber = settings_service.update_metalization_chamber(
            db,
            chamber_id,
            MetalizationChamberUpdate(chamber_number=chamber_number, mask_ids=parsed_mask_ids),
        )
    except (ValidationError, ValueError) as exc:
        return _render_settings(
            "settings_metalization_chambers.html",
            request,
            db,
            champion_id=None,
            project_id=None,
            chamber_id=chamber_id,
            error=str(exc),
            form={"chamber_number": chamber_number, "chamber_mask_ids": ",".join(mask_ids or [])},
        )
    return RedirectResponse(url=f"/ui/settings/metalization-chambers?message=Metalization+chamber+updated&chamber_id={chamber.id}", status_code=303)


@router.post("/settings/metalization-chambers/{chamber_id}/masks/add", response_model=None)
def add_metalization_chamber_mask(
    chamber_id: int,
    request: Request,
    mask_pn: str | None = Form(default=None),
    mask_id: str | None = Form(default=None),
    db: Session = Depends(get_db),
):
    enforce_admin(_current_user(request))
    try:
        parsed_mask_id = _parse_optional_int(mask_id, "Metalization mask") if mask_id is not None else None
        if not (mask_pn and mask_pn.strip()) and parsed_mask_id is None:
            raise ValueError("Metalization mask is required.")
        settings_service.add_metalization_chamber_mask(
            db,
            chamber_id,
            mask_id=parsed_mask_id,
            mask_pn=mask_pn,
        )
    except ValueError as exc:
        return _render_settings(
            "settings_metalization_chambers.html",
            request,
            db,
            champion_id=None,
            project_id=None,
            chamber_id=chamber_id,
            error=str(exc),
        )
    return RedirectResponse(url=f"/ui/settings/metalization-chambers?chamber_id={chamber_id}", status_code=303)


@router.post("/settings/metalization-chambers/{chamber_id}/masks/remove", response_model=None)
def remove_metalization_chamber_mask(
    chamber_id: int,
    request: Request,
    mask_id: str | None = Form(default=None),
    mask_pn: str | None = Form(default=None),
    db: Session = Depends(get_db),
):
    enforce_admin(_current_user(request))
    try:
        parsed_mask_id = _parse_optional_int(mask_id, "Metalization mask") if mask_id is not None else None
        settings_service.remove_metalization_chamber_mask(
            db,
            chamber_id,
            mask_id=parsed_mask_id,
            mask_pn=mask_pn,
        )
    except ValueError as exc:
        return _render_settings(
            "settings_metalization_chambers.html",
            request,
            db,
            champion_id=None,
            project_id=None,
            chamber_id=chamber_id,
            error=str(exc),
        )
    return RedirectResponse(url=f"/ui/settings/metalization-chambers?chamber_id={chamber_id}", status_code=303)


@router.post("/settings/metalization-chambers/{chamber_id}/delete", response_model=None)
def delete_metalization_chamber(chamber_id: int, request: Request, db: Session = Depends(get_db)):
    enforce_admin(_current_user(request))
    try:
        settings_service.delete_metalization_chamber(db, chamber_id)
    except ValueError as exc:
        return _render_settings("settings_metalization_chambers.html", request, db, champion_id=None, project_id=None, error=str(exc))
    return RedirectResponse(url="/ui/settings/metalization-chambers?message=Metalization+chamber+deleted", status_code=303)
