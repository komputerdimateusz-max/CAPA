from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, Form, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.core.auth import enforce_admin
from app.db.session import get_db
from app.repositories import analyses as analyses_repo
from app.repositories import champions as champions_repo
from app.services import analyses as analyses_service
from app.ui.utils import build_query_params, format_date

router = APIRouter(prefix="/ui", tags=["ui"])

TEMPLATES_DIR = Path(__file__).resolve().parents[1] / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


def _current_user(request: Request):
    return getattr(request.state, "user", None)


def _load_analysis_table(page: int, page_size: int) -> dict[str, object]:
    rows, total = analyses_service.list_analyses_page(page=page, page_size=page_size)
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
):
    table_data = _load_analysis_table(page=page, page_size=page_size)
    return templates.TemplateResponse(
        "analyses_list.html",
        {
            "request": request,
            "analyses": table_data["analyses"],
            "templates": analyses_service.list_analysis_templates(),
            "pagination": table_data["pagination"],
            "filters": {"page_size": page_size},
            "query_builder": build_query_params,
            "format_date": format_date,
        },
    )


@router.get("/analyses/_table", response_class=HTMLResponse, response_model=None)
def analyses_table(
    request: Request,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=200),
):
    table_data = _load_analysis_table(page=page, page_size=page_size)
    return templates.TemplateResponse(
        "partials/analyses_table.html",
        {
            "request": request,
            "analyses": table_data["analyses"],
            "pagination": table_data["pagination"],
            "filters": {"page_size": page_size},
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
    return RedirectResponse(url=f"/ui/analyses/{created['analysis_id']}?message=Analysis+created", status_code=303)


@router.get("/analyses/{analysis_id}", response_class=HTMLResponse, response_model=None)
def analysis_detail(
    analysis_id: str,
    request: Request,
    message: str | None = None,
):
    analysis = analyses_repo.get_analysis(analysis_id)
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis not found")
    return templates.TemplateResponse(
        "analysis_detail.html",
        {
            "request": request,
            "analysis": analysis,
            "message": message,
            "format_date": format_date,
        },
    )
