from __future__ import annotations

from datetime import date, datetime

from app.models.action import Action
from app.models.champion import Champion
from app.services.champions import score_actions, summarize_champions


def test_score_actions_on_time_close():
    champion = Champion(id=1, name="Alex")
    action = Action(
        id=10,
        title="Close on time",
        description="",
        status="CLOSED",
        created_at=datetime(2024, 1, 1, 8, 0, 0),
        due_date=date(2024, 1, 10),
        closed_at=datetime(2024, 1, 9, 8, 0, 0),
        tags=[],
    )
    action.champion = champion

    scores = score_actions([action], today=date(2024, 1, 15))

    assert scores[0].total_points == 6


def test_score_actions_late_penalties_for_open_action():
    action = Action(
        id=11,
        title="Late action",
        description="",
        status="OPEN",
        created_at=datetime(2024, 1, 1, 8, 0, 0),
        due_date=date(2024, 1, 1),
        tags=[],
    )

    scores = score_actions([action], today=date(2024, 2, 10))

    assert scores[0].total_points == -3


def test_summarize_champions_totals():
    champion = Champion(id=2, name="Jordan")
    actions = [
        Action(
            id=12,
            title="Closed",
            description="",
            status="CLOSED",
            created_at=datetime(2024, 1, 1, 8, 0, 0),
            due_date=date(2024, 1, 5),
            closed_at=datetime(2024, 1, 4, 8, 0, 0),
            tags=[],
        ),
        Action(
            id=13,
            title="Open",
            description="",
            status="OPEN",
            created_at=datetime(2024, 1, 2, 8, 0, 0),
            due_date=date(2024, 1, 5),
            tags=[],
        ),
    ]
    for action in actions:
        action.champion = champion

    scores = score_actions(actions, today=date(2024, 1, 10))
    summary = summarize_champions(scores)

    assert summary[0].actions_total == 2
    assert summary[0].actions_closed == 1
    assert summary[0].total_score == 7
