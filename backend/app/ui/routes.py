from __future__ import annotations

from datetime import date, datetime
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.repositories import actions as actions_repo
from app.services.kpi import build_actions_kpi
from app.services.metrics import calculate_action_days_late

router = APIRouter(prefix="/ui", tags=["ui"])

TEMPLATES_DIR = Path(__file__).resolve().parents[1] / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


def _format_date(value: date | datetime | None) -> str:
    if value is None:
        return "—"
    if isinstance(value, datetime):
        value = value.date()
    return value.isoformat()


def _build_action_rows(actions, subtasks) -> list[dict[str, object]]:
    subtask_map: dict[int, list] = {}
    for subtask in subtasks:
        subtask_map.setdefault(subtask.action_id, []).append(subtask)

    rows: list[dict[str, object]] = []
    for action in actions:
        days_late = calculate_action_days_late(action, subtask_map.get(action.id, []))
        rows.append(
            {
                "id": action.id,
                "title": action.title,
                "status": action.status,
                "champion": action.champion.name if action.champion else "—",
                "project": action.project.name if action.project else "—",
                "due_date": _format_date(action.due_date),
                "closed_at": _format_date(action.closed_at),
                "days_late": days_late,
            }
        )
    return rows


@router.get("/actions", response_class=HTMLResponse)
def actions_list(request: Request, deleted: int | None = None, db: Session = Depends(get_db)) -> HTMLResponse:
    actions, _total = actions_repo.list_actions(db, limit=500)
    subtasks = actions_repo.list_subtasks_for_actions(db, [action.id for action in actions])
    kpi = build_actions_kpi(actions, subtasks)
    action_rows = _build_action_rows(actions, subtasks)
    return templates.TemplateResponse(
        "actions_list.html",
        {
            "request": request,
            "actions": action_rows,
            "kpi": kpi,
            "deleted": bool(deleted),
        },
    )


@router.get("/actions/table", response_class=HTMLResponse)
def actions_table(request: Request, db: Session = Depends(get_db)) -> HTMLResponse:
    actions, _total = actions_repo.list_actions(db, limit=500)
    subtasks = actions_repo.list_subtasks_for_actions(db, [action.id for action in actions])
    action_rows = _build_action_rows(actions, subtasks)
    return templates.TemplateResponse(
        "partials/actions_table.html",
        {"request": request, "actions": action_rows},
    )


@router.get("/actions/{action_id}", response_class=HTMLResponse)
def action_detail(action_id: int, request: Request, db: Session = Depends(get_db)) -> HTMLResponse:
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
            "format_date": _format_date,
        },
    )


@router.post("/actions/{action_id}/delete")
def delete_action(action_id: int, db: Session = Depends(get_db)) -> RedirectResponse:
    action = actions_repo.get_action(db, action_id)
    if not action:
        raise HTTPException(status_code=404, detail="Action not found")
    actions_repo.delete_action(db, action)
    return RedirectResponse(url="/ui/actions?deleted=1", status_code=303)
