from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime

from app.models.action import Action
from app.models.subtask import Subtask


@dataclass
class ActionMetrics:
    days_late: int
    time_to_close_days: int | None
    on_time_close: bool | None


def _coerce_date(value: date | datetime | None) -> date | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    return value


def _calculate_delay(due_date: date | None, closed_at: date | None, today: date) -> int:
    if due_date is None:
        return 0
    if closed_at is None:
        delta = today - due_date
    else:
        delta = closed_at - due_date
    return max(0, delta.days)


def calculate_action_days_late(action: Action, subtasks: list[Subtask], today: date | None = None) -> int:
    today = today or date.today()
    if subtasks:
        total = 0
        for subtask in subtasks:
            due = _coerce_date(subtask.due_date)
            closed = _coerce_date(subtask.closed_at)
            total += _calculate_delay(due, closed, today)
        return total

    due = _coerce_date(action.due_date)
    closed = _coerce_date(action.closed_at)
    return _calculate_delay(due, closed, today)


def calculate_time_to_close_days(action: Action) -> int | None:
    if action.closed_at is None or action.created_at is None:
        return None
    return (action.closed_at - action.created_at).days


def calculate_on_time_close(action: Action) -> bool | None:
    if action.closed_at is None or action.due_date is None:
        return None
    return _coerce_date(action.closed_at) <= action.due_date


def calculate_on_time_close_rate(actions: list[Action]) -> float:
    closed_actions = [action for action in actions if action.closed_at is not None]
    if not closed_actions:
        return 0.0
    on_time = [action for action in closed_actions if calculate_on_time_close(action)]
    return len(on_time) / len(closed_actions) * 100


def build_action_metrics(action: Action, subtasks: list[Subtask], today: date | None = None) -> ActionMetrics:
    days_late = calculate_action_days_late(action, subtasks, today=today)
    time_to_close = calculate_time_to_close_days(action)
    on_time = calculate_on_time_close(action)
    return ActionMetrics(days_late=days_late, time_to_close_days=time_to_close, on_time_close=on_time)
