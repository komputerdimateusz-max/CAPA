from __future__ import annotations

from datetime import date
from pathlib import Path

from fastapi import APIRouter, Depends, Form, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.repositories import actions as actions_repo
from app.repositories import champions as champions_repo
from app.repositories import projects as projects_repo
from app.services import champions as champions_service
from app.ui.utils import build_query_params, format_date

router = APIRouter(prefix="/ui", tags=["ui"])

TEMPLATES_DIR = Path(__file__).resolve().parents[1] / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

STATUS_SCOPE_OPTIONS = (
    ("all", "All actions"),
    ("closed", "Closed only"),
)


def _filter_status_scope(actions: list, status_scope: str) -> list:
    if status_scope != "closed":
        return actions
    return [action for action in actions if (action.status or "").strip().upper() == "CLOSED"]


@router.get("/champions", response_class=HTMLResponse, response_model=None)
def champions_ranking(
    request: Request,
    from_date: date | None = Query(default=None, alias="from"),
    to_date: date | None = Query(default=None, alias="to"),
    project_id: int | None = None,
    status_scope: str = "all",
    message: str | None = None,
    db: Session = Depends(get_db),
):
    actions = actions_repo.list_actions_created_between(
        db,
        date_from=from_date,
        date_to=to_date,
        project_id=project_id,
    )
    actions = _filter_status_scope(actions, status_scope)
    valid_champion_ids = {champion.id for champion in champions_repo.list_champions(db, active_only=False)}
    scores = champions_service.score_actions(actions)
    summaries = champions_service.summarize_champions(
        scores,
        include_unassigned=True,
        valid_champion_ids=valid_champion_ids,
    )
    projects = projects_repo.list_projects(db)
    filters = {
        "from": from_date.isoformat() if from_date else "",
        "to": to_date.isoformat() if to_date else "",
        "project_id": project_id,
        "status_scope": status_scope,
    }
    return templates.TemplateResponse(
        "champions_list.html",
        {
            "request": request,
            "champions": summaries,
            "filters": filters,
            "projects": projects,
            "status_scope_options": STATUS_SCOPE_OPTIONS,
            "message": message,
        },
    )


@router.get("/champions/_table", response_class=HTMLResponse, response_model=None)
def champions_table(
    request: Request,
    from_date: date | None = Query(default=None, alias="from"),
    to_date: date | None = Query(default=None, alias="to"),
    project_id: int | None = None,
    status_scope: str = "all",
    db: Session = Depends(get_db),
):
    actions = actions_repo.list_actions_created_between(
        db,
        date_from=from_date,
        date_to=to_date,
        project_id=project_id,
    )
    actions = _filter_status_scope(actions, status_scope)
    valid_champion_ids = {champion.id for champion in champions_repo.list_champions(db, active_only=False)}
    scores = champions_service.score_actions(actions)
    summaries = champions_service.summarize_champions(
        scores,
        include_unassigned=True,
        valid_champion_ids=valid_champion_ids,
    )
    return templates.TemplateResponse(
        "partials/champions_table.html",
        {
            "request": request,
            "champions": summaries,
        },
    )


@router.post("/champions/refresh", response_model=None)
def refresh_champions(
    from_date: str = Form(default="", alias="from"),
    to_date: str = Form(default="", alias="to"),
    project_id: str = Form(default=""),
    status_scope: str = Form(default="all"),
    db: Session = Depends(get_db),
):
    sync_stats = champions_service.sync_actions_champions_with_settings(db)
    total_reassigned = (
        sync_stats.actions_updated + sync_stats.analyses_updated + sync_stats.projects_updated
    )
    if total_reassigned == 0:
        message = "No orphan champions found."
    else:
        message = (
            "Reassigned orphan champion references: "
            f"actions={sync_stats.actions_updated}, "
            f"analyses={sync_stats.analyses_updated}, "
            f"projects={sync_stats.projects_updated}."
        )
    query = build_query_params(
        {
            "from": from_date,
            "to": to_date,
            "project_id": project_id,
            "status_scope": status_scope,
            "message": message,
        }
    )
    return RedirectResponse(url=f"/ui/champions?{query}", status_code=303)


@router.get("/champions/{champion_id}", response_class=HTMLResponse, response_model=None)
def champion_detail(
    champion_id: int,
    request: Request,
    from_date: date | None = Query(default=None, alias="from"),
    to_date: date | None = Query(default=None, alias="to"),
    project_id: int | None = None,
    status_scope: str = "all",
    db: Session = Depends(get_db),
):
    champion = champions_repo.get_champion(db, champion_id)
    if not champion:
        raise HTTPException(status_code=404, detail="Champion not found")
    actions = actions_repo.list_actions_created_between(
        db,
        date_from=from_date,
        date_to=to_date,
        project_id=project_id,
        champion_id=champion_id,
    )
    actions = _filter_status_scope(actions, status_scope)
    scores = champions_service.score_actions(actions)
    summary = champions_service.summarize_champions(scores)
    summary_row = summary[0] if summary else None
    action_rows = []
    for score in scores:
        action = score.action
        action_rows.append(
            {
                "id": action.id,
                "title": action.title,
                "points": score.total_points,
                "closed_at": format_date(action.closed_at),
                "due_date": format_date(action.due_date),
                "on_time": score.on_time,
            }
        )
    filters = {
        "from": from_date.isoformat() if from_date else "",
        "to": to_date.isoformat() if to_date else "",
        "project_id": project_id,
        "status_scope": status_scope,
    }
    projects = projects_repo.list_projects(db)
    return templates.TemplateResponse(
        "champion_detail.html",
        {
            "request": request,
            "champion": champion,
            "summary": summary_row,
            "action_scores": action_rows,
            "filters": filters,
            "projects": projects,
            "status_scope_options": STATUS_SCOPE_OPTIONS,
        },
    )
