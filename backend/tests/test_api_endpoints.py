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
    )
    db_session.add(action)
    db_session.commit()

    response = client.get("/api/kpi/actions")

    assert response.status_code == 200
    payload = response.json()
    assert payload["open_count"] == 0
    assert payload["on_time_close_rate"] == 100.0


def test_project_actions_assign_and_unassign(client, db_session):
    project = Project(name="Project One", status="OPEN")
    db_session.add(project)
    db_session.flush()

    action = Action(
        title="Unassigned action",
        description="Test",
        status="OPEN",
        created_at=datetime.utcnow(),
    )
    db_session.add(action)
    db_session.commit()

    assign_response = client.post(f"/api/projects/{project.id}/actions/{action.id}")
    assert assign_response.status_code == 200
    assert assign_response.json()["project_id"] == project.id

    list_response = client.get(f"/api/projects/{project.id}/actions")
    assert list_response.status_code == 200
    assert len(list_response.json()) == 1

    unassign_response = client.delete(f"/api/projects/{project.id}/actions/{action.id}")
    assert unassign_response.status_code == 200
    assert unassign_response.json()["project_id"] is None


def test_assigning_action_in_other_project_returns_conflict(client, db_session):
    project_1 = Project(name="Project One", status="OPEN")
    project_2 = Project(name="Project Two", status="OPEN")
    db_session.add_all([project_1, project_2])
    db_session.flush()

    action = Action(
        title="Assigned action",
        description="Test",
        status="OPEN",
        project_id=project_1.id,
        created_at=datetime.utcnow(),
    )
    db_session.add(action)
    db_session.commit()

    response = client.post(f"/api/projects/{project_2.id}/actions/{action.id}")

    assert response.status_code == 409
    assert "Action is already assigned to project" in response.json()["detail"]


def test_unassigned_actions_search_filter(client, db_session):
    project = Project(name="Project One", status="OPEN")
    db_session.add(project)
    db_session.flush()

    db_session.add_all(
        [
            Action(
                title="Pump maintenance",
                description="Needs assignment",
                status="OPEN",
                created_at=datetime.utcnow(),
            ),
            Action(
                title="Weld station optimization",
                description="Already assigned",
                status="OPEN",
                project_id=project.id,
                created_at=datetime.utcnow(),
            ),
        ]
    )
    db_session.commit()

    response = client.get("/api/actions?unassigned=true&search=pump")

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 1
    assert payload["items"][0]["title"] == "Pump maintenance"
