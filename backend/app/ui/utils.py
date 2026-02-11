from __future__ import annotations

from datetime import date, datetime
from urllib.parse import urlencode

from app.models.action import Action
from app.models.subtask import Subtask
from app.services.metrics import calculate_action_days_late


def format_date(value: date | datetime | None) -> str:
    if value is None:
        return "—"
    if isinstance(value, datetime):
        value = value.date()
    return value.isoformat()


def build_query_params(filters: dict[str, object]) -> str:
    cleaned = {key: value for key, value in filters.items() if value not in (None, "", [])}
    return urlencode(cleaned, doseq=True)


def build_action_rows(actions: list[Action], subtasks: list[Subtask]) -> list[dict[str, object]]:
    subtask_map: dict[int, list[Subtask]] = {}
    for subtask in subtasks:
        subtask_map.setdefault(subtask.action_id, []).append(subtask)

    rows: list[dict[str, object]] = []
    for action in actions:
        days_late = calculate_action_days_late(action, subtask_map.get(action.id, []))
        owner = action.owner or "—"
        champion = action.champion.full_name if action.champion else "—"
        rows.append(
            {
                "id": action.id,
                "title": action.title,
                "status": action.status,
                "champion": champion,
                "owner": owner,
                "owner_display": f"{owner} / {champion}" if owner != "—" else champion,
                "project": action.project.name if action.project else "—",
                "due_date": format_date(action.due_date),
                "created_at": format_date(action.created_at),
                "closed_at": format_date(action.closed_at),
                "days_late": days_late,
                "tags": [{"id": tag.id, "name": tag.name, "color": tag.color} for tag in action.tags],
            }
        )
    return rows
