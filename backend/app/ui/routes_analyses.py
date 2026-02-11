from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, Form, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.core.auth import enforce_admin, enforce_write_access
from app.db.session import get_db
from app.repositories import analyses as analyses_repo
from app.repositories import champions as champions_repo
from app.repositories import tags as tags_repo
from app.services import analyses as analyses_service
from app.ui.utils import build_query_params, format_date

router = APIRouter(prefix="/ui", tags=["ui"])

TEMPLATES_DIR = Path(__file__).resolve().parents[1] / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


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
        },
    )


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
