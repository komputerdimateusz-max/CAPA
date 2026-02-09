from __future__ import annotations

from app.main import BlockedModeState


def _blocked_state() -> BlockedModeState:
    return BlockedModeState(
        is_blocked=True,
        database_url="sqlite:///blocked.db",
        missing_revisions=["1234abcd"],
        missing_by_table={"users": ["email"]},
    )


def test_health_reports_ok_when_not_blocked(client):
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_health_reports_blocked_payload_when_blocked(client):
    client.app.state.blocked_mode = _blocked_state()

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "blocked",
        "reason": "pending migrations",
        "action_required": "alembic upgrade head",
    }


def test_blocked_page_shows_required_details(client):
    client.app.state.blocked_mode = _blocked_state()

    response = client.get("/blocked")

    assert response.status_code == 200
    assert "Application is running in BLOCKED MODE" in response.text
    assert "Database schema is out of date." in response.text
    assert "sqlite:///blocked.db" in response.text
    assert "1234abcd" in response.text
    assert "users" in response.text
    assert "email" in response.text
    assert "cd C:\\CAPA\\backend" in response.text
    assert "call .venv\\Scripts\\activate" in response.text
    assert "alembic upgrade head" in response.text
    assert "Restart the backend after applying migrations." in response.text


def test_blocked_mode_redirects_non_allowlisted_paths(client):
    client.app.state.blocked_mode = _blocked_state()

    response = client.get("/api/actions", allow_redirects=False)

    assert response.status_code == 307
    assert response.headers["location"] == "/blocked"


def test_blocked_mode_allows_docs_and_openapi_paths(client):
    client.app.state.blocked_mode = _blocked_state()

    docs_response = client.get("/docs", allow_redirects=False)
    openapi_response = client.get("/openapi.json", allow_redirects=False)

    assert docs_response.status_code == 200
    assert openapi_response.status_code == 200
