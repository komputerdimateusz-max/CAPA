from __future__ import annotations

from datetime import date

from app.models.action import Action
from app.models.subtask import Subtask
from app.services.metrics import calculate_action_days_late, calculate_on_time_close_rate, calculate_time_to_close_days


def build_actions_kpi(
    actions: list[Action],
    subtasks: list[Subtask],
    today: date | None = None,
) -> dict[str, float | int]:
    today = today or date.today()
    subtask_map: dict[int, list[Subtask]] = {}
    for subtask in subtasks:
        subtask_map.setdefault(subtask.action_id, []).append(subtask)

    open_count = 0
    overdue_count = 0
    sum_days_late = 0
    ttc_values: list[int] = []

    for action in actions:
        if action.status.lower() != "closed":
            open_count += 1
            if action.due_date and action.due_date < today:
                overdue_count += 1
        days_late = calculate_action_days_late(action, subtask_map.get(action.id, []), today=today)
        sum_days_late += days_late
        ttc = calculate_time_to_close_days(action)
        if ttc is not None:
            ttc_values.append(ttc)

    avg_ttc = sum(ttc_values) / len(ttc_values) if ttc_values else 0.0
    on_time_rate = calculate_on_time_close_rate(actions)

    return {
        "open_count": open_count,
        "overdue_count": overdue_count,
        "on_time_close_rate": round(on_time_rate, 2),
        "avg_time_to_close_days": round(avg_ttc, 2),
        "sum_days_late": sum_days_late,
    }
