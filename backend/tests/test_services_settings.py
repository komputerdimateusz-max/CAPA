from __future__ import annotations

from datetime import date

import pytest

from app.schemas.assembly_line import AssemblyLineCreate
from app.schemas.moulding import MouldingMachineCreate, MouldingMachineUpdate, MouldingToolCreate
from app.services import settings as settings_service


def test_create_champion_unique(db_session):
    champion = settings_service.create_champion(
        db_session,
        first_name="Alex",
        last_name="Kim",
        email="alex.kim@example.com",
        position="Supervisor",
        birth_date=None,
    )

    assert champion.id is not None
    assert champion.full_name == "Alex Kim"

    with pytest.raises(ValueError, match="already exists"):
        settings_service.create_champion(
            db_session,
            first_name="Alex",
            last_name="Kim",
            email="another@example.com",
            position=None,
            birth_date=None,
        )


def test_update_project_fields(db_session):
    engineer = settings_service.create_champion(
        db_session,
        first_name="Casey",
        last_name="Ng",
        email="casey.ng@example.com",
        position="Process Engineer",
        birth_date=None,
    )
    project = settings_service.create_project(
        db_session,
        "Line Upgrade",
        "Serial production",
        1000,
        5,
        engineer.id,
        None,
    )

    updated = settings_service.update_project(
        db_session,
        project_id=project.id,
        name="Line Upgrade Phase 2",
        status="Spare Parts",
        max_volume=500,
        flex_percent=12.5,
        process_engineer_id=engineer.id,
        due_date=date(2024, 5, 1),
    )

    assert updated.name == "Line Upgrade Phase 2"
    assert updated.status == "Spare Parts"
    assert updated.max_volume == 500
    assert updated.flex_percent == 12.5
    assert updated.process_engineer_id == engineer.id
    assert updated.due_date == date(2024, 5, 1)


def test_create_project_validates_required_fields(db_session):
    with pytest.raises(ValueError, match="Project status is required"):
        settings_service.create_project(db_session, "Line", None, 0, 10, 1, None)

    engineer = settings_service.create_champion(
        db_session,
        first_name="Sam",
        last_name="Fox",
        email="sam.fox@example.com",
        position="Process Engineer",
        birth_date=None,
    )

    with pytest.raises(ValueError, match="must be one of"):
        settings_service.create_project(db_session, "Line", "Open", 0, 10, engineer.id, None)
    with pytest.raises(ValueError, match="greater than or equal to 0"):
        settings_service.create_project(db_session, "Line", "Serial production", -1, 10, engineer.id, None)
    with pytest.raises(ValueError, match="between 0 and 100"):
        settings_service.create_project(db_session, "Line", "Serial production", 1, 120, engineer.id, None)
    with pytest.raises(ValueError, match="does not exist"):
        settings_service.create_project(db_session, "Line", "Serial production", 1, 10, 9999, None)


def test_create_and_list_moulding_tool(db_session):
    created = settings_service.create_moulding_tool(
        db_session,
        MouldingToolCreate(tool_pn="T-100", description="Main tool", ct_seconds=12.5),
    )

    tools = settings_service.list_moulding_tools(db_session)

    assert created.id is not None
    assert len(tools) == 1
    assert tools[0].tool_pn == "T-100"
    assert tools[0].ct_seconds == 12.5


def test_create_moulding_tool_unique_tool_pn(db_session):
    settings_service.create_moulding_tool(
        db_session,
        MouldingToolCreate(tool_pn="T-200", description=None, ct_seconds=8),
    )

    with pytest.raises(ValueError, match="Tool P/N already exists"):
        settings_service.create_moulding_tool(
            db_session,
            MouldingToolCreate(tool_pn="T-200", description="Dup", ct_seconds=9),
        )


def test_create_moulding_machine_with_tool_assignments(db_session):
    tool_a = settings_service.create_moulding_tool(
        db_session,
        MouldingToolCreate(tool_pn="T-A", description=None, ct_seconds=10),
    )
    tool_b = settings_service.create_moulding_tool(
        db_session,
        MouldingToolCreate(tool_pn="T-B", description=None, ct_seconds=11),
    )

    machine = settings_service.create_moulding_machine(
        db_session,
        MouldingMachineCreate(
            machine_number="M-01",
            tonnage=250,
            tool_ids=[tool_a.id, tool_b.id],
        ),
    )

    assert machine.id is not None
    assert machine.machine_number == "M-01"
    assert sorted(tool.tool_pn for tool in machine.tools) == ["T-A", "T-B"]


def test_update_moulding_machine_assignments_replace_list(db_session):
    tool_a = settings_service.create_moulding_tool(
        db_session,
        MouldingToolCreate(tool_pn="T-01", description=None, ct_seconds=10),
    )
    tool_b = settings_service.create_moulding_tool(
        db_session,
        MouldingToolCreate(tool_pn="T-02", description=None, ct_seconds=12),
    )
    tool_c = settings_service.create_moulding_tool(
        db_session,
        MouldingToolCreate(tool_pn="T-03", description=None, ct_seconds=14),
    )
    machine = settings_service.create_moulding_machine(
        db_session,
        MouldingMachineCreate(machine_number="M-55", tonnage=180, tool_ids=[tool_a.id, tool_b.id]),
    )

    updated = settings_service.update_moulding_machine(
        db_session,
        machine.id,
        MouldingMachineUpdate(machine_number="M-55", tonnage=200, tool_ids=[tool_c.id]),
    )

    assert updated.tonnage == 200
    assert [tool.tool_pn for tool in updated.tools] == ["T-03"]


def test_list_moulding_machines_returns_assigned_tools(db_session):
    tool = settings_service.create_moulding_tool(
        db_session,
        MouldingToolCreate(tool_pn="T-LIST", description="Listed", ct_seconds=6),
    )
    settings_service.create_moulding_machine(
        db_session,
        MouldingMachineCreate(machine_number="M-LIST", tonnage=None, tool_ids=[tool.id]),
    )

    machines = settings_service.list_moulding_machines(db_session)

    assert len(machines) == 1
    assert machines[0].machine_number == "M-LIST"
    assert [(assigned.id, assigned.tool_pn) for assigned in machines[0].tools] == [(tool.id, "T-LIST")]


def test_create_assembly_line_and_list_order(db_session):
    settings_service.create_assembly_line(
        db_session,
        AssemblyLineCreate(line_number="20", ct_seconds=8.5, hc=3),
    )
    created = settings_service.create_assembly_line(
        db_session,
        AssemblyLineCreate(line_number="10", ct_seconds=12, hc=5),
    )

    assembly_lines = settings_service.list_assembly_lines(db_session)

    assert created.id is not None
    assert [line.line_number for line in assembly_lines] == ["10", "20"]


def test_create_assembly_line_requires_unique_line_number(db_session):
    settings_service.create_assembly_line(
        db_session,
        AssemblyLineCreate(line_number="L-01", ct_seconds=10, hc=2),
    )

    with pytest.raises(ValueError, match="Line number already exists"):
        settings_service.create_assembly_line(
            db_session,
            AssemblyLineCreate(line_number="L-01", ct_seconds=11, hc=4),
        )
