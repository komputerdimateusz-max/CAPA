from __future__ import annotations

from app.core.config import settings
from app.models.user import User

def test_ui_settings_page(client):
    response = client.get("/ui/settings")

    assert response.status_code == 200


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
