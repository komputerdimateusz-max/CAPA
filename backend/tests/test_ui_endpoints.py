from __future__ import annotations

from datetime import datetime

from sqlalchemy.exc import OperationalError

from app.core.config import settings
from app.models.action import Action
from app.models.project import Project
from app.models.user import User
from app.schemas.assembly_line import AssemblyLineCreate
from app.schemas.moulding import MouldingToolCreate
from app.services import settings as settings_service


def test_ui_settings_page(client):
    response = client.get("/ui/settings")

    assert response.status_code == 200
    assert "Global Settings" in response.text
    assert "Moulding Machines" in response.text
    assert "Assembly Lines" in response.text


def test_ui_settings_champions_subpage(client):
    response = client.get("/ui/settings/champions")

    assert response.status_code == 200
    assert "Back to Settings" in response.text
    assert "Add champion" in response.text


def test_ui_analyses_page(client, monkeypatch, tmp_path):
    monkeypatch.setenv("CAPA_DATA_DIR", str(tmp_path))

    response = client.get("/ui/analyses")

    assert response.status_code == 200


def test_ui_signup_creates_user_and_sets_cookie(client, db_session):
    response = client.post(
        "/ui/signup",
        data={"username": "new-user", "password": "secure-pass"},
        allow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"] == "/ui"
    assert settings.session_cookie_name in response.headers.get("set-cookie", "")

    created = db_session.query(User).filter(User.username == "new-user").one()
    assert created.role == "viewer"


def test_ui_index_redirects_to_login_when_unauthenticated(client):
    response = client.get("/ui", allow_redirects=False)

    assert response.status_code == 302
    assert response.headers["location"] == "/login"


def test_login_alias_redirects_to_ui_login(client):
    response = client.get("/login", allow_redirects=False)

    assert response.status_code == 302
    assert response.headers["location"] == "/ui/login"


def test_login_shows_schema_error_when_users_email_missing(client, monkeypatch):
    def _raise_operational_error(db, username):
        raise OperationalError("SELECT users.email FROM users", {}, Exception("no such column: users.email"))

    monkeypatch.setattr("app.ui.routes_auth.users_repo.get_user_by_username", _raise_operational_error)

    response = client.post("/ui/login", data={"username": "u", "password": "p"})

    assert response.status_code == 500
    assert "Database schema is out of date" in response.text
    assert "alembic upgrade head" in response.text


def test_action_detail_edit_contains_project_select(client, db_session):
    project = Project(name="Project A", status="OPEN")
    action = Action(title="Action A", status="OPEN", created_at=datetime.utcnow())
    db_session.add_all([project, action])
    db_session.commit()

    response = client.get(f"/ui/actions/{action.id}?edit=1")

    assert response.status_code == 200
    assert 'name="project_id"' in response.text
    assert "Project" in response.text


def test_project_detail_contains_actions_manager_controls(client, db_session):
    project = Project(name="Project A", status="OPEN")
    unassigned = Action(title="Unassigned A", status="OPEN", created_at=datetime.utcnow())
    db_session.add_all([project, unassigned])
    db_session.commit()

    response = client.get(f"/ui/projects/{project.id}")

    assert response.status_code == 200
    assert "Actions in this project" in response.text
    assert "Search unassigned actions" in response.text
    assert "Add action" in response.text


def test_ui_settings_shows_users_section(client, db_session):
    db_session.add(
        User(
            username="alice",
            email="alice@example.com",
            password_hash="hash",
            role="viewer",
            is_active=True,
        )
    )
    db_session.commit()

    response = client.get("/ui/settings/users")

    assert response.status_code == 200
    assert "Users" in response.text
    assert "alice@example.com" in response.text


def test_ui_settings_updates_user_role(client, db_session):
    user = User(
        username="alice",
        email="alice@example.com",
        password_hash="hash",
        role="viewer",
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()

    response = client.post(f"/ui/settings/users/{user.id}/role", data={"role": "admin"}, allow_redirects=False)

    assert response.status_code == 303
    db_session.refresh(user)
    assert user.role == "admin"


def test_ui_settings_assembly_lines_subpage(client):
    response = client.get("/ui/settings/assembly-lines")

    assert response.status_code == 200
    assert "Assembly Lines" in response.text
    assert "Add assembly line" in response.text


def test_ui_project_assignment_endpoints_and_assignments_page(client, db_session):
    engineer = settings_service.create_champion(
        db_session,
        first_name="Kai",
        last_name="Long",
        email="kai.long@example.com",
        position="Process Engineer",
        birth_date=None,
    )
    tool = settings_service.create_moulding_tool(
        db_session,
        MouldingToolCreate(tool_pn="UI-T1", description="Lens", ct_seconds=10),
    )
    line = settings_service.create_assembly_line(
        db_session,
        AssemblyLineCreate(line_number="UI-L1", ct_seconds=8, hc=3),
    )
    project = settings_service.create_project(
        db_session,
        "UI Project",
        "Serial production",
        100,
        10,
        engineer.id,
        None,
    )

    add_tool_resp = client.post(
        f"/ui/settings/projects/{project.id}/tools/add",
        data={"tool_id": str(tool.id)},
        allow_redirects=False,
    )
    add_line_resp = client.post(
        f"/ui/settings/projects/{project.id}/lines/add",
        data={"line_id": str(line.id)},
        allow_redirects=False,
    )

    assert add_tool_resp.status_code == 303
    assert add_line_resp.status_code == 303

    assignments_resp = client.get(f"/ui/settings/projects/{project.id}/assignments")
    assert assignments_resp.status_code == 200
    assert "Project Assignments" in assignments_resp.text
    assert "UI-T1" in assignments_resp.text
    assert "UI-L1" in assignments_resp.text

    remove_tool_resp = client.post(
        f"/ui/settings/projects/{project.id}/tools/remove",
        data={"tool_id": str(tool.id)},
        allow_redirects=False,
    )
    remove_line_resp = client.post(
        f"/ui/settings/projects/{project.id}/lines/remove",
        data={"line_id": str(line.id)},
        allow_redirects=False,
    )

    assert remove_tool_resp.status_code == 303
    assert remove_line_resp.status_code == 303


def test_ui_settings_projects_table_has_assignments_links(client, db_session):
    engineer = settings_service.create_champion(
        db_session,
        first_name="Mia",
        last_name="Stone",
        email="mia.stone@example.com",
        position="Process Engineer",
        birth_date=None,
    )
    project = settings_service.create_project(
        db_session,
        "Linked Project",
        "Serial production",
        50,
        7,
        engineer.id,
        None,
    )

    response = client.get("/ui/settings/projects")

    assert response.status_code == 200
    assert f'/ui/settings/projects/{project.id}/assignments' in response.text
