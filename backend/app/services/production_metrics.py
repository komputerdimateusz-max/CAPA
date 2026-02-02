from __future__ import annotations

from datetime import date

from app.models.action import Action
from app.models.subtask import Subtask
from app.services.kpi import build_actions_kpi


def build_daily_kpi_rows(
    actions: list[Action],
    subtasks: list[Subtask],
) -> list[dict[str, object]]:
    subtasks_by_action: dict[int, list[Subtask]] = {}
    for subtask in subtasks:
        subtasks_by_action.setdefault(subtask.action_id, []).append(subtask)

    actions_by_day: dict[date, list[Action]] = {}
    for action in actions:
        if action.created_at:
            actions_by_day.setdefault(action.created_at.date(), []).append(action)

    rows: list[dict[str, object]] = []
    for day, day_actions in sorted(actions_by_day.items(), key=lambda item: item[0]):
        day_subtasks = []
        for action in day_actions:
            day_subtasks.extend(subtasks_by_action.get(action.id, []))
        kpi = build_actions_kpi(day_actions, day_subtasks, today=day)
        rows.append(
            {
                "date": day,
                "total_actions": len(day_actions),
                "open_count": kpi["open_count"],
                "overdue_count": kpi["overdue_count"],
                "on_time_close_rate": kpi["on_time_close_rate"],
                "avg_time_to_close_days": kpi["avg_time_to_close_days"],
                "sum_days_late": kpi["sum_days_late"],
            }
        )

    return rows
