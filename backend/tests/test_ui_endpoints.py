from __future__ import annotations

from datetime import datetime

from sqlalchemy.exc import OperationalError

from app.core.config import settings
from app.models.action import Action
from app.models.project import Project
from app.models.user import User
from app.schemas.assembly_line import AssemblyLineCreate
from app.schemas.metalization import MetalizationMaskCreate
from app.schemas.moulding import MouldingMachineCreate, MouldingToolCreate
from app.services import settings as settings_service


def test_ui_settings_page(client):
    response = client.get("/ui/settings")

    assert response.status_code == 200
    assert "Global Settings" in response.text
    assert "Moulding Machines" in response.text
    assert "Assembly Lines" in response.text
    assert "Metalization Masks" in response.text
    assert "Metalization Chambers" in response.text
    assert "Labour cost" in response.text


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



def test_ui_moulding_machine_tools_page_and_count_link(client, db_session):
    tool_a = settings_service.create_moulding_tool(
        db_session,
        MouldingToolCreate(tool_pn="000001", description="Tool A", ct_seconds=10),
    )
    tool_b = settings_service.create_moulding_tool(
        db_session,
        MouldingToolCreate(tool_pn="000002", description="Tool B", ct_seconds=12),
    )
    machine = settings_service.create_moulding_machine(
        db_session,
        MouldingMachineCreate(machine_number="MC-01", tonnage=120, tool_ids=[tool_b.id, tool_a.id]),
    )

    list_response = client.get("/ui/settings/moulding-machines")
    assert list_response.status_code == 200
    assert f'href="/ui/settings/moulding-machines/{machine.id}/tools">2</a>' in list_response.text

    tools_response = client.get(f"/ui/settings/moulding-machines/{machine.id}/tools")
    assert tools_response.status_code == 200
    assert "Moulding Machine Tools" in tools_response.text
    assert "Machine: MC-01" in tools_response.text
    assert "000001" in tools_response.text
    assert "000002" in tools_response.text


def test_ui_moulding_machine_tools_page_returns_404_for_missing_machine(client):
    response = client.get("/ui/settings/moulding-machines/999999/tools")

    assert response.status_code == 404

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
    mask = settings_service.create_metalization_mask(
        db_session,
        MetalizationMaskCreate(mask_pn="UI-M1", description="Coating", ct_seconds=9),
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
    add_mask_resp = client.post(
        f"/ui/settings/projects/{project.id}/metalization-masks/add",
        data={"mask_pn": "ui-m1"},
        allow_redirects=False,
    )

    assert add_tool_resp.status_code == 303
    assert add_line_resp.status_code == 303
    assert add_mask_resp.status_code == 303

    assignments_resp = client.get(f"/ui/settings/projects/{project.id}/assignments")
    assert assignments_resp.status_code == 200
    assert "Project Assignments" in assignments_resp.text
    assert "UI-T1" in assignments_resp.text
    assert "UI-L1" in assignments_resp.text
    assert "UI-M1" in assignments_resp.text

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
    remove_mask_resp = client.post(
        f"/ui/settings/projects/{project.id}/metalization-masks/remove",
        data={"mask_id": str(mask.id)},
        allow_redirects=False,
    )

    assert remove_tool_resp.status_code == 303
    assert remove_line_resp.status_code == 303
    assert remove_mask_resp.status_code == 303



def test_ui_project_add_line_by_line_number_and_unknown_validation(client, db_session):
    engineer = settings_service.create_champion(
        db_session,
        first_name="Lin",
        last_name="Park",
        email="lin.park@example.com",
        position="Process Engineer",
        birth_date=None,
    )
    line = settings_service.create_assembly_line(
        db_session,
        AssemblyLineCreate(line_number="PL74", ct_seconds=55.0, hc=19),
    )
    project = settings_service.create_project(
        db_session,
        "Line Search Project",
        "Serial production",
        100,
        10,
        engineer.id,
        None,
    )

    add_line_resp = client.post(
        f"/ui/settings/projects/{project.id}/lines/add",
        data={"line_number": "pl74"},
        allow_redirects=False,
    )

    assert add_line_resp.status_code == 303
    db_session.refresh(project)
    assert [assigned_line.id for assigned_line in project.assembly_lines] == [line.id]

    unknown_line_resp = client.post(
        f"/ui/settings/projects/{project.id}/lines/add",
        data={"line_number": "PL999"},
        allow_redirects=False,
    )

    assert unknown_line_resp.status_code == 303
    assert "error=Unknown+line+number" in unknown_line_resp.headers["location"]

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
    assert "0 masks" in response.text


def test_ui_settings_labour_cost_page_and_update(client):
    response = client.get("/ui/settings/labour-cost")

    assert response.status_code == 200
    for worker_type in ("Operator", "Logistic", "TeamLeader", "Inspector", "Specialist", "Technican"):
        assert worker_type in response.text

    update_response = client.post(
        "/ui/settings/labour-cost/update",
        data={"worker_type": "Operator", "cost_pln": "123.45"},
        allow_redirects=False,
    )

    assert update_response.status_code == 303
    assert "message=Labour+cost+updated" in update_response.headers["location"]


def test_ui_settings_labour_cost_validation_errors(client):
    invalid_worker_response = client.post(
        "/ui/settings/labour-cost/update",
        data={"worker_type": "Unknown", "cost_pln": "100"},
        allow_redirects=False,
    )
    invalid_cost_response = client.post(
        "/ui/settings/labour-cost/update",
        data={"worker_type": "Operator", "cost_pln": "-1"},
        allow_redirects=False,
    )

    assert invalid_worker_response.status_code == 303
    assert "error=" in invalid_worker_response.headers["location"]
    assert invalid_cost_response.status_code == 303
    assert "error=" in invalid_cost_response.headers["location"]
