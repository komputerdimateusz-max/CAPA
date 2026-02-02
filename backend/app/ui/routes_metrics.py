from __future__ import annotations

from datetime import date
from pathlib import Path

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.repositories import actions as actions_repo
from app.services.production_metrics import build_daily_kpi_rows

router = APIRouter(prefix="/ui", tags=["ui"])

TEMPLATES_DIR = Path(__file__).resolve().parents[1] / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


def _load_daily_kpis(
    db: Session,
    from_date: date | None,
    to_date: date | None,
) -> list[dict[str, object]]:
    actions = actions_repo.list_actions_created_between(db, date_from=from_date, date_to=to_date)
    subtasks = actions_repo.list_subtasks_for_actions(db, [action.id for action in actions])
    return build_daily_kpi_rows(actions, subtasks)


@router.get("/explorer", response_class=HTMLResponse, response_model=None)
def explorer_dashboard(
    request: Request,
    from_date: date | None = Query(default=None, alias="from"),
    to_date: date | None = Query(default=None, alias="to"),
    db: Session = Depends(get_db),
):
    rows = _load_daily_kpis(db, from_date, to_date)
    filters = {
        "from": from_date.isoformat() if from_date else "",
        "to": to_date.isoformat() if to_date else "",
    }
    return templates.TemplateResponse(
        "explorer.html",
        {
            "request": request,
            "rows": rows,
            "filters": filters,
        },
    )


@router.get("/explorer/_table", response_class=HTMLResponse, response_model=None)
def explorer_table(
    request: Request,
    from_date: date | None = Query(default=None, alias="from"),
    to_date: date | None = Query(default=None, alias="to"),
    db: Session = Depends(get_db),
):
    rows = _load_daily_kpis(db, from_date, to_date)
    return templates.TemplateResponse(
        "partials/metrics_table.html",
        {
            "request": request,
            "rows": rows,
        },
    )


@router.get("/kpi", response_class=HTMLResponse, response_model=None)
def kpi_dashboard(
    request: Request,
    from_date: date | None = Query(default=None, alias="from"),
    to_date: date | None = Query(default=None, alias="to"),
    db: Session = Depends(get_db),
):
    rows = _load_daily_kpis(db, from_date, to_date)
    filters = {
        "from": from_date.isoformat() if from_date else "",
        "to": to_date.isoformat() if to_date else "",
    }
    return templates.TemplateResponse(
        "kpi_dashboard.html",
        {
            "request": request,
            "rows": rows,
            "filters": filters,
        },
    )


@router.get("/kpi/_table", response_class=HTMLResponse, response_model=None)
def kpi_table(
    request: Request,
    from_date: date | None = Query(default=None, alias="from"),
    to_date: date | None = Query(default=None, alias="to"),
    db: Session = Depends(get_db),
):
    rows = _load_daily_kpis(db, from_date, to_date)
    return templates.TemplateResponse(
        "partials/metrics_table.html",
        {
            "request": request,
            "rows": rows,
        },
    )
