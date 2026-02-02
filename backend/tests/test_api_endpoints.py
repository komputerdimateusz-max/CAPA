from __future__ import annotations

from datetime import date, datetime

from app.models.action import Action
from app.models.project import Project


def test_get_actions(client, db_session):
    project = Project(name="Line A", status="OPEN")
    db_session.add(project)
    db_session.commit()
    db_session.refresh(project)

    action = Action(
        title="Reduce scrap",
        description="Test",
        project_id=project.id,
        status="OPEN",
        created_at=datetime(2024, 1, 1, 8, 0, 0),
        due_date=date(2024, 1, 5),
        tags=["scrap"],
    )
    db_session.add(action)
    db_session.commit()

    response = client.get("/api/actions")

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 1
    assert payload["items"][0]["title"] == "Reduce scrap"


def test_get_actions_kpi(client, db_session):
    action = Action(
        title="Close on time",
        description="Test",
        status="CLOSED",
        created_at=datetime(2024, 1, 1, 8, 0, 0),
        due_date=date(2024, 1, 3),
        closed_at=datetime(2024, 1, 2, 8, 0, 0),
        tags=[],
    )
    db_session.add(action)
    db_session.commit()

    response = client.get("/api/kpi/actions")

    assert response.status_code == 200
    payload = response.json()
    assert payload["open_count"] == 0
    assert payload["on_time_close_rate"] == 100.0
