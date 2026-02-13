from __future__ import annotations

from datetime import datetime

from sqlalchemy.exc import OperationalError

from app.core.config import settings
from app.models.action import Action
from app.models.project import Project
from app.models.user import User


def test_ui_settings_page(client):
    response = client.get("/ui/settings")

    assert response.status_code == 200
    assert "Global Settings" in response.text
    assert "Moulding Machines" in response.text


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
