from __future__ import annotations

from datetime import date, datetime
from pathlib import Path

from fastapi import APIRouter, Depends, Form, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.auth import enforce_admin, enforce_write_access
from app.db.session import get_db
from app.models.action import Action
from app.models.analysis import (
    ALLOWED_OBSERVED_PROCESS_TYPES,
    Analysis5Why,
    OBSERVED_PROCESS_TYPE_ASSEMBLY,
    OBSERVED_PROCESS_TYPE_METALIZATION,
    OBSERVED_PROCESS_TYPE_MOULDING,
)
from app.models.champion import Champion
from app.repositories import actions as actions_repo
from app.repositories import analyses as analyses_repo
from app.repositories import champions as champions_repo
from app.repositories import tags as tags_repo
from app.services import analyses as analyses_service
from app.ui.utils import build_query_params, format_date

router = APIRouter(prefix="/ui", tags=["ui"])

TEMPLATES_DIR = Path(__file__).resolve().parents[1] / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

ROOT_CAUSE_CATEGORIES = ["Process", "Material", "Method", "Man", "Machine", "Management"]

OBSERVED_PROCESS_LABELS = {
    OBSERVED_PROCESS_TYPE_ASSEMBLY: "Assembly",
    OBSERVED_PROCESS_TYPE_MOULDING: "Moulding",
    OBSERVED_PROCESS_TYPE_METALIZATION: "Metalization",
}


def _validate_observed_process_type(value: str | None) -> str | None:
    normalized = (value or "").strip().lower()
    if not normalized:
        return None
    if normalized not in ALLOWED_OBSERVED_PROCESS_TYPES:
        raise HTTPException(status_code=422, detail="Observed process must be assembly, moulding, or metalization")
    return normalized


def _ensure_5why_details(db: Session, analysis_id: str, *, problem_statement: str = "Pending problem", root_cause: str = "Pending root cause") -> Analysis5Why:
    details = analyses_repo.get_analysis_5why(db, analysis_id)
    if details is None:
        details = Analysis5Why(analysis_id=analysis_id, problem_statement=problem_statement, root_cause=root_cause)
        details = analyses_repo.update_analysis_5why(db, details)
    return details


def _observed_component_count(details: Analysis5Why | None) -> int:
    if not details or not details.observed_process_type:
        return 0
    if details.observed_process_type == OBSERVED_PROCESS_TYPE_MOULDING:
        return len(details.moulding_tools)
    if details.observed_process_type == OBSERVED_PROCESS_TYPE_METALIZATION:
        return len(details.metalization_masks)
    if details.observed_process_type == OBSERVED_PROCESS_TYPE_ASSEMBLY:
        return len(details.assembly_references)
    return 0


def _current_user(request: Request):
    return getattr(request.state, "user", None)


def _load_analysis_table(db: Session, page: int, page_size: int, tags: list[str] | None) -> dict[str, object]:
    rows, total = analyses_service.list_analyses_page(db, page=page, page_size=page_size, tags=tags)
    total_pages = max(1, (total + page_size - 1) // page_size)
    return {
        "analyses": rows,
        "pagination": {
            "total": total,
            "total_pages": total_pages,
            "page": page,
            "page_size": page_size,
        },
    }


def _resolve_champion_id(db: Session, full_name: str | None) -> int | None:
    normalized = (full_name or "").strip().lower()
    if not normalized:
        return None
    stmt = (
        db.query(Champion)
        .filter(func.lower(func.trim(Champion.first_name + " " + Champion.last_name)) == normalized)
        .limit(1)
    )
    champion = stmt.one_or_none()
    return champion.id if champion else None


def _parse_optional_date(value: str | None) -> date | None:
    if not value:
        return None
    return date.fromisoformat(value)


@router.get("/analyses", response_class=HTMLResponse, response_model=None)
def analyses_list(
    request: Request,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=200),
    tags: list[str] | None = Query(default=None),
    db: Session = Depends(get_db),
):
    table_data = _load_analysis_table(db, page=page, page_size=page_size, tags=tags)
    return templates.TemplateResponse(
        "analyses_list.html",
        {
            "request": request,
            "analyses": table_data["analyses"],
            "templates": analyses_service.list_analysis_templates(),
            "pagination": table_data["pagination"],
            "filters": {"page_size": page_size, "tags": tags or []},
            "all_tags": tags_repo.list_tags(db),
            "query_builder": build_query_params,
            "format_date": format_date,
        },
    )


@router.get("/analyses/_table", response_class=HTMLResponse, response_model=None)
def analyses_table(
    request: Request,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=200),
    tags: list[str] | None = Query(default=None),
    db: Session = Depends(get_db),
):
    table_data = _load_analysis_table(db, page=page, page_size=page_size, tags=tags)
    return templates.TemplateResponse(
        "partials/analyses_table.html",
        {
            "request": request,
            "analyses": table_data["analyses"],
            "pagination": table_data["pagination"],
            "filters": {"page_size": page_size, "tags": tags or []},
            "query_builder": build_query_params,
            "format_date": format_date,
        },
    )


@router.get("/analyses/new", response_class=HTMLResponse, response_model=None)
def analyses_new(
    request: Request,
    analysis_type: str | None = Query(default=None, alias="type"),
    db: Session = Depends(get_db),
):
    champions = champions_repo.list_champions(db)
    template_options = analyses_service.list_analysis_templates()
    template_codes = {template.code for template in template_options}
    normalized_type = analysis_type.upper() if analysis_type else None
    default_type = normalized_type if normalized_type in template_codes else template_options[0].code
    return templates.TemplateResponse(
        "analysis_new.html",
        {
            "request": request,
            "templates": template_options,
            "champions": champions,
            "form": {"analysis_type": default_type},
        },
    )


@router.post("/analyses", response_model=None)
def create_analysis(
    request: Request,
    analysis_type: str = Form(...),
    title: str = Form(...),
    description: str = Form(default=""),
    champion: str = Form(default=""),
    db: Session = Depends(get_db),
):
    enforce_admin(_current_user(request))
    champions = champions_repo.list_champions(db)
    template_options = analyses_service.list_analysis_templates()
    try:
        created = analyses_service.create_analysis(
            db,
            analysis_type=analysis_type,
            title=title,
            description=description,
            champion=champion,
        )
    except ValueError as exc:
        return templates.TemplateResponse(
            "analysis_new.html",
            {
                "request": request,
                "templates": template_options,
                "champions": champions,
                "error": str(exc),
                "form": {
                    "analysis_type": analysis_type,
                    "title": title,
                    "description": description,
                    "champion": champion,
                },
            },
        )
    return RedirectResponse(url=f"/ui/analyses/{created.id}?message=Analysis+created", status_code=303)


@router.get("/analyses/{analysis_id}", response_class=HTMLResponse, response_model=None)
def analysis_detail(
    analysis_id: str,
    request: Request,
    message: str | None = None,
    db: Session = Depends(get_db),
):
    analysis = analyses_repo.get_analysis(db, analysis_id)
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis not found")
    return templates.TemplateResponse(
        "analysis_detail.html",
        {
            "request": request,
            "analysis": analysis,
            "all_tags": tags_repo.list_tags(db),
            "message": message,
            "format_date": format_date,
            "root_cause_categories": ROOT_CAUSE_CATEGORIES,
            "observed_process_labels": OBSERVED_PROCESS_LABELS,
            "moulding_tools": actions_repo.list_moulding_tools(db),
            "metalization_masks": actions_repo.list_metalization_masks(db),
            "assembly_references": actions_repo.list_assembly_references(db),
            "observed_components_count": _observed_component_count(analysis.details_5why),
        },
    )


@router.post("/analyses/{analysis_id}/save-5why", response_model=None)
def save_analysis_5why(
    analysis_id: str,
    request: Request,
    problem_statement: str = Form(...),
    where_observed: str = Form(default=""),
    observed_process_type: str | None = Form(default=None),
    date_detected: str | None = Form(default=None),
    why_1: str = Form(default=""),
    why_2: str = Form(default=""),
    why_3: str = Form(default=""),
    why_4: str = Form(default=""),
    why_5: str = Form(default=""),
    root_cause: str = Form(...),
    root_cause_category: str = Form(default=""),
    containment_action: str = Form(default=""),
    proposed_action: str = Form(default=""),
    db: Session = Depends(get_db),
):
    analysis = analyses_repo.get_analysis(db, analysis_id)
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis not found")
    enforce_write_access(_current_user(request))

    problem_value = problem_statement.strip()
    root_cause_value = root_cause.strip()
    if not problem_value or not root_cause_value:
        return RedirectResponse(
            url=f"/ui/analyses/{analysis_id}?message=Problem+statement+and+root+cause+are+required",
            status_code=303,
        )

    details = analyses_repo.get_analysis_5why(db, analysis_id)
    if details is None:
        details = Analysis5Why(analysis_id=analysis_id, problem_statement=problem_value, root_cause=root_cause_value)

    details.problem_statement = problem_value
    details.where_observed = where_observed.strip() or None
    details.observed_process_type = _validate_observed_process_type(observed_process_type)
    details.date_detected = _parse_optional_date(date_detected)
    details.why_1 = why_1.strip() or None
    details.why_2 = why_2.strip() or None
    details.why_3 = why_3.strip() or None
    details.why_4 = why_4.strip() or None
    details.why_5 = why_5.strip() or None
    details.root_cause = root_cause_value
    details.root_cause_category = root_cause_category.strip() or None
    details.containment_action = containment_action.strip() or None
    details.proposed_action = proposed_action.strip() or None

    analyses_repo.update_analysis_5why(db, details)
    return RedirectResponse(url=f"/ui/analyses/{analysis_id}?message=Analysis+saved", status_code=303)


@router.post("/analyses/{analysis_id}/observed/set-process", response_model=None)
def set_observed_process(
    analysis_id: str,
    request: Request,
    process_type: str | None = Form(default=None),
    db: Session = Depends(get_db),
):
    analysis = analyses_repo.get_analysis(db, analysis_id)
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis not found")
    enforce_write_access(_current_user(request))

    details = _ensure_5why_details(db, analysis_id)
    normalized_process = _validate_observed_process_type(process_type)
    component_ids: list[int] = []
    if normalized_process == details.observed_process_type:
        if normalized_process == OBSERVED_PROCESS_TYPE_MOULDING:
            component_ids = [tool.id for tool in details.moulding_tools]
        elif normalized_process == OBSERVED_PROCESS_TYPE_METALIZATION:
            component_ids = [mask.id for mask in details.metalization_masks]
        elif normalized_process == OBSERVED_PROCESS_TYPE_ASSEMBLY:
            component_ids = [reference.id for reference in details.assembly_references]
    analyses_repo.set_analysis_observed_components(db, analysis_id, normalized_process, component_ids)
    return RedirectResponse(url=f"/ui/analyses/{analysis_id}", status_code=303)


@router.post("/analyses/{analysis_id}/observed/moulding-tools/add", response_model=None)
def add_observed_moulding_tool(
    analysis_id: str,
    request: Request,
    tool_id: str | None = Form(None),
    tool_pn: str | None = Form(None),
    db: Session = Depends(get_db),
):
    analysis = analyses_repo.get_analysis(db, analysis_id)
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis not found")
    enforce_write_access(_current_user(request))

    details = _ensure_5why_details(db, analysis_id)
    if details.observed_process_type != OBSERVED_PROCESS_TYPE_MOULDING:
        raise HTTPException(status_code=400, detail="Observed process_type must be moulding")

    tool = actions_repo.get_moulding_tool_by_id(db, int(tool_id)) if tool_id else None
    if tool is None and tool_pn:
        tool = actions_repo.get_moulding_tool_by_pn(db, tool_pn.strip())
    if not tool:
        raise HTTPException(status_code=404, detail="Moulding tool not found")

    component_ids = [existing.id for existing in details.moulding_tools]
    if tool.id not in component_ids:
        component_ids.append(tool.id)
    analyses_repo.set_analysis_observed_components(db, analysis_id, OBSERVED_PROCESS_TYPE_MOULDING, component_ids)
    return RedirectResponse(url=f"/ui/analyses/{analysis_id}", status_code=303)


@router.post("/analyses/{analysis_id}/observed/moulding-tools/remove", response_model=None)
def remove_observed_moulding_tool(
    analysis_id: str,
    request: Request,
    tool_id: int = Form(...),
    db: Session = Depends(get_db),
):
    analysis = analyses_repo.get_analysis(db, analysis_id)
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis not found")
    enforce_write_access(_current_user(request))

    details = _ensure_5why_details(db, analysis_id)
    component_ids = [existing.id for existing in details.moulding_tools if existing.id != tool_id]
    analyses_repo.set_analysis_observed_components(db, analysis_id, OBSERVED_PROCESS_TYPE_MOULDING, component_ids)
    return RedirectResponse(url=f"/ui/analyses/{analysis_id}", status_code=303)


@router.post("/analyses/{analysis_id}/observed/metalization-masks/add", response_model=None)
def add_observed_metalization_mask(
    analysis_id: str,
    request: Request,
    mask_id: str | None = Form(None),
    mask_pn: str | None = Form(None),
    db: Session = Depends(get_db),
):
    analysis = analyses_repo.get_analysis(db, analysis_id)
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis not found")
    enforce_write_access(_current_user(request))

    details = _ensure_5why_details(db, analysis_id)
    if details.observed_process_type != OBSERVED_PROCESS_TYPE_METALIZATION:
        raise HTTPException(status_code=400, detail="Observed process_type must be metalization")

    mask = actions_repo.get_metalization_mask_by_id(db, int(mask_id)) if mask_id else None
    if mask is None and mask_pn:
        mask = actions_repo.get_metalization_mask_by_pn(db, mask_pn.strip())
    if not mask:
        raise HTTPException(status_code=404, detail="Metalization mask not found")

    component_ids = [existing.id for existing in details.metalization_masks]
    if mask.id not in component_ids:
        component_ids.append(mask.id)
    analyses_repo.set_analysis_observed_components(db, analysis_id, OBSERVED_PROCESS_TYPE_METALIZATION, component_ids)
    return RedirectResponse(url=f"/ui/analyses/{analysis_id}", status_code=303)


@router.post("/analyses/{analysis_id}/observed/metalization-masks/remove", response_model=None)
def remove_observed_metalization_mask(
    analysis_id: str,
    request: Request,
    mask_id: int = Form(...),
    db: Session = Depends(get_db),
):
    analysis = analyses_repo.get_analysis(db, analysis_id)
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis not found")
    enforce_write_access(_current_user(request))

    details = _ensure_5why_details(db, analysis_id)
    component_ids = [existing.id for existing in details.metalization_masks if existing.id != mask_id]
    analyses_repo.set_analysis_observed_components(db, analysis_id, OBSERVED_PROCESS_TYPE_METALIZATION, component_ids)
    return RedirectResponse(url=f"/ui/analyses/{analysis_id}", status_code=303)


@router.post("/analyses/{analysis_id}/observed/assembly-references/add", response_model=None)
def add_observed_assembly_reference(
    analysis_id: str,
    request: Request,
    reference_id: str | None = Form(None),
    reference_name: str | None = Form(None),
    db: Session = Depends(get_db),
):
    analysis = analyses_repo.get_analysis(db, analysis_id)
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis not found")
    enforce_write_access(_current_user(request))

    details = _ensure_5why_details(db, analysis_id)
    if details.observed_process_type != OBSERVED_PROCESS_TYPE_ASSEMBLY:
        raise HTTPException(status_code=400, detail="Observed process_type must be assembly")

    reference = actions_repo.get_assembly_reference_by_id(db, int(reference_id)) if reference_id else None
    if reference is None and reference_name:
        reference = actions_repo.get_assembly_reference_by_name(db, reference_name.strip())
    if not reference:
        raise HTTPException(status_code=404, detail="Assembly reference not found")

    component_ids = [existing.id for existing in details.assembly_references]
    if reference.id not in component_ids:
        component_ids.append(reference.id)
    analyses_repo.set_analysis_observed_components(db, analysis_id, OBSERVED_PROCESS_TYPE_ASSEMBLY, component_ids)
    return RedirectResponse(url=f"/ui/analyses/{analysis_id}", status_code=303)


@router.post("/analyses/{analysis_id}/observed/assembly-references/remove", response_model=None)
def remove_observed_assembly_reference(
    analysis_id: str,
    request: Request,
    reference_id: int = Form(...),
    db: Session = Depends(get_db),
):
    analysis = analyses_repo.get_analysis(db, analysis_id)
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis not found")
    enforce_write_access(_current_user(request))

    details = _ensure_5why_details(db, analysis_id)
    component_ids = [existing.id for existing in details.assembly_references if existing.id != reference_id]
    analyses_repo.set_analysis_observed_components(db, analysis_id, OBSERVED_PROCESS_TYPE_ASSEMBLY, component_ids)
    return RedirectResponse(url=f"/ui/analyses/{analysis_id}", status_code=303)


@router.post("/analyses/{analysis_id}/create-action", response_model=None)
def create_action_from_analysis(
    analysis_id: str,
    request: Request,
    db: Session = Depends(get_db),
):
    analysis = analyses_repo.get_analysis(db, analysis_id)
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis not found")
    enforce_write_access(_current_user(request))

    details = analysis.details_5why
    if not details or not details.problem_statement or not details.root_cause:
        return RedirectResponse(
            url=f"/ui/analyses/{analysis_id}?message=Save+Problem+statement+and+Root+cause+before+creating+an+action",
            status_code=303,
        )

    description_parts = [details.root_cause]
    if details.proposed_action:
        description_parts.append(details.proposed_action)

    action = Action(
        title=f"Action from 5WHY: {details.problem_statement}",
        description="\n\n".join(description_parts),
        champion_id=_resolve_champion_id(db, analysis.champion),
        status="OPEN",
        created_at=datetime.utcnow(),
        process_type="moulding",
    )
    created = actions_repo.create_action(db, action)

    if all(linked.id != created.id for linked in analysis.actions):
        analysis.actions.append(created)
        analyses_repo.update_analysis(db, analysis)

    return RedirectResponse(url=f"/ui/actions/{created.id}?edit=1", status_code=303)


@router.post("/analyses/{analysis_id}/tags", response_model=None)
def add_analysis_tag(
    analysis_id: str,
    request: Request,
    tag_name: str = Form(...),
    db: Session = Depends(get_db),
):
    analysis = analyses_repo.get_analysis(db, analysis_id)
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis not found")
    enforce_write_access(_current_user(request))
    tag = tags_repo.get_or_create_tag(db, tag_name)
    if tag not in analysis.tags:
        analysis.tags.append(tag)
    analyses_repo.update_analysis(db, analysis)
    return RedirectResponse(url=f"/ui/analyses/{analysis_id}", status_code=303)


@router.post("/analyses/{analysis_id}/tags/{tag_id}/delete", response_model=None)
def remove_analysis_tag(
    analysis_id: str,
    tag_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    analysis = analyses_repo.get_analysis(db, analysis_id)
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis not found")
    enforce_write_access(_current_user(request))
    analysis.tags = [tag for tag in analysis.tags if tag.id != tag_id]
    analyses_repo.update_analysis(db, analysis)
    return RedirectResponse(url=f"/ui/analyses/{analysis_id}", status_code=303)
