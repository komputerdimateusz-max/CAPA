from __future__ import annotations

from datetime import date, datetime

from app.models.action import Action
from app.models.subtask import Subtask
from app.services.metrics import (
    calculate_action_days_late,
    calculate_on_time_close,
    calculate_on_time_close_rate,
    calculate_time_to_close_days,
)


def test_days_late_with_subtasks():
    action = Action(
        title="Test",
        description="",
        status="OPEN",
        created_at=datetime(2024, 1, 1, 8, 0, 0),
        due_date=date(2024, 1, 10),
        tags=[],
    )
    subtasks = [
        Subtask(
            action_id=1,
            title="A",
            status="OPEN",
            due_date=date(2024, 1, 5),
            created_at=datetime(2024, 1, 1, 8, 0, 0),
        ),
        Subtask(
            action_id=1,
            title="B",
            status="DONE",
            due_date=date(2024, 1, 3),
            closed_at=datetime(2024, 1, 4, 9, 0, 0),
            created_at=datetime(2024, 1, 1, 8, 0, 0),
        ),
    ]

    days_late = calculate_action_days_late(action, subtasks, today=date(2024, 1, 7))

    assert days_late == 3  # (7-5)=2 + (4-3)=1


def test_days_late_without_subtasks_uses_action_dates():
    action = Action(
        title="Test",
        description="",
        status="OPEN",
        created_at=datetime(2024, 1, 1, 8, 0, 0),
        due_date=date(2024, 1, 5),
        tags=[],
    )

    days_late = calculate_action_days_late(action, [], today=date(2024, 1, 7))

    assert days_late == 2


def test_time_to_close_and_on_time_close():
    action = Action(
        title="Closed",
        description="",
        status="CLOSED",
        created_at=datetime(2024, 1, 1, 8, 0, 0),
        due_date=date(2024, 1, 10),
        closed_at=datetime(2024, 1, 9, 8, 0, 0),
        tags=[],
    )

    assert calculate_time_to_close_days(action) == 8
    assert calculate_on_time_close(action) is True


def test_on_time_close_rate():
    actions = [
        Action(
            title="A",
            description="",
            status="CLOSED",
            created_at=datetime(2024, 1, 1, 8, 0, 0),
            due_date=date(2024, 1, 5),
            closed_at=datetime(2024, 1, 4, 8, 0, 0),
            tags=[],
        ),
        Action(
            title="B",
            description="",
            status="CLOSED",
            created_at=datetime(2024, 1, 1, 8, 0, 0),
            due_date=date(2024, 1, 5),
            closed_at=datetime(2024, 1, 6, 8, 0, 0),
            tags=[],
        ),
    ]

    rate = calculate_on_time_close_rate(actions)

    assert rate == 50.0
