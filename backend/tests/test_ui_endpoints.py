from __future__ import annotations

from datetime import date, datetime

from sqlalchemy.exc import OperationalError

from app.core.config import settings
from app.models.action import Action
from app.models.project import Project
from app.models.user import User
from app.schemas.assembly_line import AssemblyLineCreate, AssemblyLineReferenceCreate
from app.schemas.material import MaterialCreate
from app.schemas.metalization import MetalizationChamberCreate, MetalizationMaskCreate
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
    assert "Materials" in response.text
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



def test_ui_metalization_chamber_masks_page_and_count_link(client, db_session):
    mask_a = settings_service.create_metalization_mask(
        db_session,
        MetalizationMaskCreate(mask_pn="M00002", description="Mask B", ct_seconds=10),
    )
    mask_b = settings_service.create_metalization_mask(
        db_session,
        MetalizationMaskCreate(mask_pn="M00001", description="Mask A", ct_seconds=12),
    )
    chamber = settings_service.create_metalization_chamber(
        db_session,
        data=MetalizationChamberCreate(
            chamber_number="CH-01",
            mask_ids=[mask_a.id, mask_b.id],
        ),
    )

    list_response = client.get("/ui/settings/metalization-chambers")
    assert list_response.status_code == 200
    assert f'href="/ui/settings/metalization-chambers/{chamber.id}/masks">2</a>' in list_response.text

    masks_response = client.get(f"/ui/settings/metalization-chambers/{chamber.id}/masks")
    assert masks_response.status_code == 200
    assert "Metalization Chamber Masks" in masks_response.text
    assert "Chamber: CH-01" in masks_response.text
    assert "M00001" in masks_response.text
    assert "M00002" in masks_response.text


def test_ui_materials_crud_endpoints(client, db_session):
    create_response = client.post(
        "/ui/settings/materials",
        data={"part_number": "MAT-01", "description": "Granulate", "unit": "kg", "price_per_unit": "9.5", "category": "Raw material", "make_buy": "1"},
        allow_redirects=False,
    )
    assert create_response.status_code == 303

    list_response = client.get("/ui/settings/materials")
    assert list_response.status_code == 200
    assert "Materials" in list_response.text
    assert "MAT-01" in list_response.text

    material = settings_service.list_materials(db_session)[0]
    update_response = client.post(
        f"/ui/settings/materials/{material.id}",
        data={"part_number": "MAT-01", "description": "Updated", "unit": "pcs", "price_per_unit": "11", "category": "FG"},
        allow_redirects=False,
    )
    assert update_response.status_code == 303

    duplicate_response = client.post(
        "/ui/settings/materials",
        data={"part_number": "mat-01", "description": "Dup", "unit": "pcs", "price_per_unit": "1", "category": "metal parts"},
        allow_redirects=True,
    )
    assert duplicate_response.status_code == 200
    assert "already exists" in duplicate_response.text

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


def test_ui_moulding_tools_list_shows_hc_total_unit_and_material_cost(client, db_session):
    settings_service.update_labour_cost(db_session, "Operator", 10)
    tool = settings_service.create_moulding_tool(
        db_session,
        MouldingToolCreate(tool_pn="UI-HC-T", description="desc", ct_seconds=60, hc_map={"Operator": 2}),
    )
    material_a = settings_service.create_material(
        db_session,
        MaterialCreate(part_number="UI-MAT-T-1", description="mat-a", unit="kg", price_per_unit=3, category="Raw material", make_buy=False),
    )
    material_b = settings_service.create_material(
        db_session,
        MaterialCreate(part_number="UI-MAT-T-2", description="mat-b", unit="kg", price_per_unit=4, category="metal parts", make_buy=True),
    )
    settings_service.add_material_to_tool(db_session, tool.id, material_id=material_a.id, qty_per_piece=2)
    settings_service.add_material_to_tool(db_session, tool.id, material_id=material_b.id, qty_per_piece=1.5)

    response = client.get("/ui/settings/moulding-tools")

    assert response.status_code == 200
    assert "HC total" in response.text
    assert "Unit labour cost avg [PLN]" in response.text
    assert "Material cost [PLN]" in response.text
    assert "0.33" in response.text
    assert "12.00" in response.text


def test_ui_metalization_masks_list_shows_hc_total_unit_and_material_cost(client, db_session):
    settings_service.update_labour_cost(db_session, "Operator", 10)
    mask = settings_service.create_metalization_mask(
        db_session,
        MetalizationMaskCreate(mask_pn="UI-HC-M", description="desc", ct_seconds=60, hc_map={"Operator": 1.5}),
    )
    material = settings_service.create_material(
        db_session,
        MaterialCreate(part_number="UI-MAT-M-1", description="mat", unit="ml", price_per_unit=10, category="sub-group", make_buy=False),
    )
    settings_service.add_material_to_mask(db_session, mask.id, material_id=material.id, qty_per_piece=0.5)

    response = client.get("/ui/settings/metalization-masks")

    assert response.status_code == 200
    assert "HC total" in response.text
    assert "Unit labour cost avg [PLN]" in response.text
    assert "Material cost [PLN]" in response.text
    assert "0.25" in response.text
    assert "5.00" in response.text


def test_ui_add_moulding_tool_persists_hc_breakdown(client, db_session):
    response = client.post(
        "/ui/settings/moulding-tools",
        data={
            "tool_pn": "UI-HC-T2",
            "description": "x",
            "ct_seconds": "60",
            "hc_operator": "1.25",
            "hc_logistic": "0.75",
            "hc_teamleader": "0",
            "hc_inspector": "0",
            "hc_specialist": "0",
            "hc_technican": "0",
        },
        allow_redirects=False,
    )
    assert response.status_code == 303
    tool = next(t for t in settings_service.list_moulding_tools(db_session) if t.tool_pn == "UI-HC-T2")
    hc_map = settings_service.get_tool_hc_map(db_session, tool.id)
    assert hc_map["Operator"] == 1.25
    assert hc_map["Logistic"] == 0.75


def test_ui_lists_show_outcome_material_cost_columns(client, db_session):
    tool = settings_service.create_moulding_tool(
        db_session,
        MouldingToolCreate(tool_pn="UI-OUT-T", description="desc", ct_seconds=60, hc_map={"Operator": 1}),
    )
    mask = settings_service.create_metalization_mask(
        db_session,
        MetalizationMaskCreate(mask_pn="UI-OUT-M", description="desc", ct_seconds=60, hc_map={"Operator": 1}),
    )
    material = settings_service.create_material(
        db_session,
        MaterialCreate(part_number="UI-OUT-MAT", description="mat", unit="kg", price_per_unit=2, category="Raw material", make_buy=False),
    )
    settings_service.add_material_out_to_tool(db_session, tool.id, material_id=material.id, qty_per_piece=3)
    settings_service.add_material_out_to_mask(db_session, mask.id, material_id=material.id, qty_per_piece=4)

    tool_response = client.get("/ui/settings/moulding-tools")
    mask_response = client.get("/ui/settings/metalization-masks")

    assert tool_response.status_code == 200
    assert mask_response.status_code == 200
    assert "Outcome material cost [PLN]" in tool_response.text
    assert "Outcome material cost [PLN]" in mask_response.text
    assert "6.00" in tool_response.text
    assert "8.00" in mask_response.text


def test_ui_assembly_lines_list_shows_labour_and_material_costs(client, db_session):
    settings_service.update_labour_cost(db_session, "Operator", 12)
    line = settings_service.create_assembly_line(
        db_session,
        AssemblyLineCreate(line_number="UI-AL-1", ct_seconds=60, hc=0, hc_map={"Operator": 2}),
    )
    material = settings_service.create_material(
        db_session,
        MaterialCreate(part_number="UI-AL-MAT", description="mat", unit="kg", price_per_unit=5, category="FG", make_buy=True),
    )
    settings_service.add_material_in_to_assembly_line(db_session, line.id, material_id=material.id, qty_per_piece=1)
    settings_service.add_material_out_to_assembly_line(db_session, line.id, material_id=material.id, qty_per_piece=0.2)

    response = client.get("/ui/settings/assembly-lines")

    assert response.status_code == 200
    assert "Unit labour cost avg [PLN]" in response.text
    assert "Outcome cost avg [PLN]" in response.text
    assert "0.40" in response.text
    assert "5.00" in response.text


def test_ui_assembly_line_references_page_and_average_link(client, db_session):
    line = settings_service.create_assembly_line(
        db_session,
        AssemblyLineCreate(line_number="UI-AL-REF-1", ct_seconds=10, hc=0),
    )
    fg = settings_service.create_material(
        db_session,
        MaterialCreate(part_number="UI-AL-REF-FG", description="fg", unit="pc", price_per_unit=2, category="FG", make_buy=False),
    )
    settings_service.create_assembly_line_reference(
        db_session,
        line.id,
        AssemblyLineReferenceCreate(reference_name="R1", fg_material_id=fg.id, ct_seconds=12, hc_map={"Operator": 1}),
    )

    list_response = client.get("/ui/settings/assembly-lines")
    ref_response = client.get(f"/ui/settings/assembly-lines/{line.id}/references")

    assert list_response.status_code == 200
    assert f'href="/ui/settings/assembly-lines/{line.id}/references">1</a>' in list_response.text
    assert ref_response.status_code == 200
    assert "Assembly Line References" in ref_response.text
    assert "R1" in ref_response.text


def test_ui_action_add_remove_moulding_tools(client, db_session):
    tool = settings_service.create_moulding_tool(
        db_session,
        MouldingToolCreate(tool_pn="T-100", description="Form", ct_seconds=10),
    )
    action = Action(title="Moulding action", status="OPEN", process_type="moulding", created_at=datetime.utcnow())
    db_session.add(action)
    db_session.commit()

    add_response = client.post(
        f"/ui/actions/{action.id}/moulding-tools/add",
        data={"tool_pn": "T-100"},
        allow_redirects=False,
    )
    assert add_response.status_code == 303

    db_session.refresh(action)
    assert [item.tool_pn for item in action.moulding_tools] == [tool.tool_pn]

    remove_response = client.post(
        f"/ui/actions/{action.id}/moulding-tools/remove",
        data={"tool_id": tool.id},
        allow_redirects=False,
    )
    assert remove_response.status_code == 303
    db_session.refresh(action)
    assert action.moulding_tools == []


def test_ui_action_add_remove_metalization_masks(client, db_session):
    mask = settings_service.create_metalization_mask(
        db_session,
        MetalizationMaskCreate(mask_pn="M-200", description="Mask", ct_seconds=11),
    )
    action = Action(title="Metalization action", status="OPEN", process_type="metalization", created_at=datetime.utcnow())
    db_session.add(action)
    db_session.commit()

    add_response = client.post(
        f"/ui/actions/{action.id}/metalization-masks/add",
        data={"mask_pn": "M-200"},
        allow_redirects=False,
    )
    assert add_response.status_code == 303

    db_session.refresh(action)
    assert [item.mask_pn for item in action.metalization_masks] == [mask.mask_pn]

    remove_response = client.post(
        f"/ui/actions/{action.id}/metalization-masks/remove",
        data={"mask_id": mask.id},
        allow_redirects=False,
    )
    assert remove_response.status_code == 303
    db_session.refresh(action)
    assert action.metalization_masks == []


def test_ui_action_add_remove_assembly_references(client, db_session):
    fg = settings_service.create_material(
        db_session,
        MaterialCreate(part_number="FG-10", description="FG", unit="pcs", price_per_unit=1.0, category="FG"),
    )
    line = settings_service.create_assembly_line(db_session, AssemblyLineCreate(line_number="L-1", labor_cost_per_h=20.0))
    reference = settings_service.create_assembly_line_reference(
        db_session,
        line.id,
        AssemblyLineReferenceCreate(reference_name="REF-1", fg_part_number=fg.part_number, ct_seconds=8),
    )
    action = Action(title="Assembly action", status="OPEN", process_type="assembly", created_at=datetime.utcnow())
    db_session.add(action)
    db_session.commit()

    add_response = client.post(
        f"/ui/actions/{action.id}/assembly-references/add",
        data={"reference_name": "REF-1"},
        allow_redirects=False,
    )
    assert add_response.status_code == 303

    db_session.refresh(action)
    assert [item.reference_name for item in action.assembly_references] == [reference.reference_name]

    remove_response = client.post(
        f"/ui/actions/{action.id}/assembly-references/remove",
        data={"reference_id": reference.id},
        allow_redirects=False,
    )
    assert remove_response.status_code == 303
    db_session.refresh(action)
    assert action.assembly_references == []


def test_switching_process_clears_old_assignments(client, db_session):
    tool = settings_service.create_moulding_tool(
        db_session,
        MouldingToolCreate(tool_pn="T-101", description="Form", ct_seconds=10),
    )
    action = Action(title="Switch process", status="OPEN", process_type="moulding", created_at=datetime.utcnow())
    action.moulding_tools.append(tool)
    db_session.add(action)
    db_session.commit()

    response = client.post(
        f"/ui/actions/{action.id}/edit",
        data={
            "title": action.title,
            "description": "",
            "status": "OPEN",
            "champion_id": "",
            "owner": "",
            "due_date": "",
            "project_id": "",
            "priority": "",
            "process_type": "assembly",
        },
        allow_redirects=False,
    )

    assert response.status_code == 303
    db_session.refresh(action)
    assert action.process_type == "assembly"
    assert action.moulding_tools == []


from app.models.analysis import Analysis, Analysis5Why


def test_analysis_detail_renders_5why_form(client, db_session):
    analysis = Analysis(
        id="5WHY-2026-0002",
        type="5WHY",
        title="Defect investigation",
        description="",
        champion="Alex Smith",
        status="Open",
        created_at=date.today(),
        closed_at=None,
    )
    db_session.add(analysis)
    db_session.commit()

    response = client.get(f"/ui/analyses/{analysis.id}")

    assert response.status_code == 200
    assert "Problem statement" in response.text
    assert "Create Action from this Analysis" in response.text


def test_save_5why_and_create_linked_action(client, db_session):
    analysis = Analysis(
        id="5WHY-2026-0003",
        type="5WHY",
        title="Seal issue",
        description="",
        champion="",
        status="Open",
        created_at=date.today(),
        closed_at=None,
    )
    db_session.add(analysis)
    db_session.commit()

    save_response = client.post(
        f"/ui/analyses/{analysis.id}/save-5why",
        data={
            "problem_statement": "Leakage at station 4",
            "root_cause": "Incorrect torque setup",
            "proposed_action": "Lock torque settings and retrain operators",
        },
        allow_redirects=False,
    )
    assert save_response.status_code == 303

    details = db_session.get(Analysis5Why, analysis.id)
    assert details is not None
    assert details.problem_statement == "Leakage at station 4"

    create_response = client.post(f"/ui/analyses/{analysis.id}/create-action", allow_redirects=False)
    assert create_response.status_code == 303
    assert create_response.headers["location"].startswith("/ui/actions/")

    db_session.refresh(analysis)
    assert len(analysis.actions) == 1
    assert analysis.actions[0].title.startswith("Action from 5WHY")
