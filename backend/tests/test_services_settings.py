from __future__ import annotations

from datetime import date

import pytest
from sqlalchemy import select

from app.models.assembly_line import ProjectAssemblyLine
from app.models.metalization import ProjectMetalizationMask
from app.models.moulding import ProjectMouldingTool
from app.schemas.assembly_line import AssemblyLineCreate
from app.schemas.metalization import MetalizationChamberCreate, MetalizationMaskCreate
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



def test_create_project_with_tools_and_lines(db_session):
    engineer = settings_service.create_champion(
        db_session,
        first_name="Jordan",
        last_name="Miles",
        email="jordan.miles@example.com",
        position="Process Engineer",
        birth_date=None,
    )
    tool_a = settings_service.create_moulding_tool(
        db_session,
        MouldingToolCreate(tool_pn="P-100", description="A", ct_seconds=10),
    )
    tool_b = settings_service.create_moulding_tool(
        db_session,
        MouldingToolCreate(tool_pn="P-200", description="B", ct_seconds=12),
    )
    line = settings_service.create_assembly_line(
        db_session,
        AssemblyLineCreate(line_number="L-100", ct_seconds=8, hc=3),
    )

    project = settings_service.create_project(
        db_session,
        "Project A",
        "Serial production",
        100,
        10,
        engineer.id,
        None,
        moulding_tool_ids=[tool_a.id, tool_b.id, tool_a.id],
        assembly_line_ids=[line.id],
    )

    assert {tool.id for tool in project.moulding_tools} == {tool_a.id, tool_b.id}
    assert [assigned_line.id for assigned_line in project.assembly_lines] == [line.id]


def test_update_project_replaces_tools_and_lines(db_session):
    engineer = settings_service.create_champion(
        db_session,
        first_name="Taylor",
        last_name="Ray",
        email="taylor.ray@example.com",
        position="Process Engineer",
        birth_date=None,
    )
    tool_a = settings_service.create_moulding_tool(db_session, MouldingToolCreate(tool_pn="U-1", description=None, ct_seconds=10))
    tool_b = settings_service.create_moulding_tool(db_session, MouldingToolCreate(tool_pn="U-2", description=None, ct_seconds=12))
    line_a = settings_service.create_assembly_line(db_session, AssemblyLineCreate(line_number="UL-1", ct_seconds=9, hc=2))
    line_b = settings_service.create_assembly_line(db_session, AssemblyLineCreate(line_number="UL-2", ct_seconds=7, hc=4))

    project = settings_service.create_project(
        db_session,
        "Project B",
        "Serial production",
        100,
        10,
        engineer.id,
        None,
        moulding_tool_ids=[tool_a.id],
        assembly_line_ids=[line_a.id],
    )

    updated = settings_service.update_project(
        db_session,
        project.id,
        "Project B",
        "Spare Parts",
        100,
        11,
        engineer.id,
        None,
        moulding_tool_ids=[tool_b.id],
        assembly_line_ids=[line_b.id],
    )

    assert [tool.id for tool in updated.moulding_tools] == [tool_b.id]
    assert [line.id for line in updated.assembly_lines] == [line_b.id]




def test_add_project_assignments_is_idempotent(db_session):
    engineer = settings_service.create_champion(
        db_session,
        first_name="Dana",
        last_name="Cole",
        email="dana.cole@example.com",
        position="Process Engineer",
        birth_date=None,
    )
    tool = settings_service.create_moulding_tool(
        db_session,
        MouldingToolCreate(tool_pn="IDEMP-1", description=None, ct_seconds=10),
    )
    line = settings_service.create_assembly_line(
        db_session,
        AssemblyLineCreate(line_number="IDEMP-L1", ct_seconds=9, hc=2),
    )
    project = settings_service.create_project(
        db_session,
        "Project I",
        "Serial production",
        100,
        5,
        engineer.id,
        None,
    )

    settings_service.add_project_moulding_tool(db_session, project.id, tool.id)
    updated = settings_service.add_project_moulding_tool(db_session, project.id, tool.id)
    settings_service.add_project_assembly_line(db_session, project.id, line.id)
    updated = settings_service.add_project_assembly_line(db_session, project.id, line.id)

    assert [assigned_tool.id for assigned_tool in updated.moulding_tools] == [tool.id]
    assert [assigned_line.id for assigned_line in updated.assembly_lines] == [line.id]


def test_remove_project_assignments_is_safe_when_missing(db_session):
    engineer = settings_service.create_champion(
        db_session,
        first_name="Noa",
        last_name="Perry",
        email="noa.perry@example.com",
        position="Process Engineer",
        birth_date=None,
    )
    project = settings_service.create_project(
        db_session,
        "Project Safe",
        "Serial production",
        80,
        6,
        engineer.id,
        None,
    )

    updated = settings_service.remove_project_moulding_tool(db_session, project.id, 999)
    updated = settings_service.remove_project_assembly_line(db_session, project.id, 999)

    assert updated.moulding_tools == []
    assert updated.assembly_lines == []


def test_delete_project_cascades_assignment_rows(db_session):
    engineer = settings_service.create_champion(
        db_session,
        first_name="Robin",
        last_name="Lee",
        email="robin.lee@example.com",
        position="Process Engineer",
        birth_date=None,
    )
    tool = settings_service.create_moulding_tool(db_session, MouldingToolCreate(tool_pn="C-1", description=None, ct_seconds=10))
    line = settings_service.create_assembly_line(db_session, AssemblyLineCreate(line_number="CL-1", ct_seconds=8, hc=2))
    project = settings_service.create_project(
        db_session,
        "Project C",
        "Serial production",
        120,
        5,
        engineer.id,
        None,
        moulding_tool_ids=[tool.id],
        assembly_line_ids=[line.id],
    )

    db_session.delete(project)
    db_session.commit()

    assert db_session.scalars(select(ProjectMouldingTool)).all() == []
    assert db_session.scalars(select(ProjectAssemblyLine)).all() == []


def test_project_assignment_validation_rejects_non_existing_ids(db_session):
    engineer = settings_service.create_champion(
        db_session,
        first_name="Ari",
        last_name="Chen",
        email="ari.chen@example.com",
        position="Process Engineer",
        birth_date=None,
    )

    with pytest.raises(ValueError, match="moulding tools do not exist"):
        settings_service.create_project(
            db_session,
            "Project D",
            "Serial production",
            200,
            5,
            engineer.id,
            None,
            moulding_tool_ids=[999],
            assembly_line_ids=[],
        )

    with pytest.raises(ValueError, match="assembly lines do not exist"):
        settings_service.create_project(
            db_session,
            "Project E",
            "Serial production",
            200,
            5,
            engineer.id,
            None,
            moulding_tool_ids=[],
            assembly_line_ids=[999],
        )

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


def test_create_and_list_metalization_mask(db_session):
    created = settings_service.create_metalization_mask(
        db_session,
        MetalizationMaskCreate(mask_pn="M-100", description="Main mask", ct_seconds=13.5),
    )

    masks = settings_service.list_metalization_masks(db_session)

    assert created.id is not None
    assert len(masks) == 1
    assert masks[0].mask_pn == "M-100"


def test_create_metalization_mask_unique_mask_pn(db_session):
    settings_service.create_metalization_mask(
        db_session,
        MetalizationMaskCreate(mask_pn="M-200", description=None, ct_seconds=8),
    )

    with pytest.raises(ValueError, match="Mask P/N already exists"):
        settings_service.create_metalization_mask(
            db_session,
            MetalizationMaskCreate(mask_pn="M-200", description="Dup", ct_seconds=9),
        )


def test_create_metalization_chamber_with_mask_assignments(db_session):
    mask_a = settings_service.create_metalization_mask(
        db_session,
        MetalizationMaskCreate(mask_pn="MC-A", description=None, ct_seconds=10),
    )
    mask_b = settings_service.create_metalization_mask(
        db_session,
        MetalizationMaskCreate(mask_pn="MC-B", description=None, ct_seconds=11),
    )

    chamber = settings_service.create_metalization_chamber(
        db_session,
        MetalizationChamberCreate(chamber_number="C-01", mask_ids=[mask_a.id, mask_b.id]),
    )

    assert chamber.id is not None
    assert sorted(mask.mask_pn for mask in chamber.masks) == ["MC-A", "MC-B"]


def test_project_metalization_assignments_add_remove_and_cascade(db_session):
    engineer = settings_service.create_champion(
        db_session,
        first_name="Metal",
        last_name="Engineer",
        email="metal.engineer@example.com",
        position="Process Engineer",
        birth_date=None,
    )
    mask = settings_service.create_metalization_mask(
        db_session,
        MetalizationMaskCreate(mask_pn="PM-1", description=None, ct_seconds=10),
    )
    project = settings_service.create_project(
        db_session,
        "Project Metal",
        "Serial production",
        120,
        5,
        engineer.id,
        None,
    )

    updated = settings_service.add_project_metalization_mask(db_session, project.id, mask.id)
    updated = settings_service.add_project_metalization_mask(db_session, project.id, mask.id)
    assert [assigned.mask_pn for assigned in updated.metalization_masks] == ["PM-1"]

    removed = settings_service.remove_project_metalization_mask(db_session, project.id, mask.id)
    assert removed.metalization_masks == []

    settings_service.add_project_metalization_mask(db_session, project.id, mask.id)
    db_session.delete(project)
    db_session.commit()

    assert db_session.scalars(select(ProjectMetalizationMask)).all() == []


def test_add_tool_to_moulding_machine_by_tool_pn(db_session):
    tool = settings_service.create_moulding_tool(
        db_session,
        MouldingToolCreate(tool_pn="TM-ADD", description=None, ct_seconds=10),
    )
    machine = settings_service.create_moulding_machine(
        db_session,
        MouldingMachineCreate(machine_number="M-ADD", tonnage=100, tool_ids=[]),
    )

    updated = settings_service.add_moulding_machine_tool(db_session, machine.id, tool_pn="tm-add")

    assert [assigned.tool_pn for assigned in updated.tools] == [tool.tool_pn]


def test_remove_tool_from_moulding_machine(db_session):
    tool = settings_service.create_moulding_tool(
        db_session,
        MouldingToolCreate(tool_pn="TM-REMOVE", description=None, ct_seconds=10),
    )
    machine = settings_service.create_moulding_machine(
        db_session,
        MouldingMachineCreate(machine_number="M-REMOVE", tonnage=100, tool_ids=[tool.id]),
    )

    updated = settings_service.remove_moulding_machine_tool(db_session, machine.id, tool_id=tool.id)

    assert updated.tools == []


def test_add_mask_to_chamber_by_mask_pn(db_session):
    mask = settings_service.create_metalization_mask(
        db_session,
        MetalizationMaskCreate(mask_pn="MSK-ADD", description=None, ct_seconds=10),
    )
    chamber = settings_service.create_metalization_chamber(
        db_session,
        MetalizationChamberCreate(chamber_number="C-ADD", mask_ids=[]),
    )

    updated = settings_service.add_metalization_chamber_mask(db_session, chamber.id, mask_pn="msk-add")

    assert [assigned.mask_pn for assigned in updated.masks] == [mask.mask_pn]


def test_remove_mask_from_chamber(db_session):
    mask = settings_service.create_metalization_mask(
        db_session,
        MetalizationMaskCreate(mask_pn="MSK-REMOVE", description=None, ct_seconds=10),
    )
    chamber = settings_service.create_metalization_chamber(
        db_session,
        MetalizationChamberCreate(chamber_number="C-REMOVE", mask_ids=[mask.id]),
    )

    updated = settings_service.remove_metalization_chamber_mask(db_session, chamber.id, mask_id=mask.id)

    assert updated.masks == []


def test_machine_and_chamber_assignment_add_is_idempotent(db_session):
    tool = settings_service.create_moulding_tool(
        db_session,
        MouldingToolCreate(tool_pn="TM-IDEMP", description=None, ct_seconds=10),
    )
    machine = settings_service.create_moulding_machine(
        db_session,
        MouldingMachineCreate(machine_number="M-IDEMP", tonnage=100, tool_ids=[]),
    )
    mask = settings_service.create_metalization_mask(
        db_session,
        MetalizationMaskCreate(mask_pn="MSK-IDEMP", description=None, ct_seconds=10),
    )
    chamber = settings_service.create_metalization_chamber(
        db_session,
        MetalizationChamberCreate(chamber_number="C-IDEMP", mask_ids=[]),
    )

    settings_service.add_moulding_machine_tool(db_session, machine.id, tool_pn=tool.tool_pn)
    updated_machine = settings_service.add_moulding_machine_tool(db_session, machine.id, tool_id=tool.id)
    settings_service.add_metalization_chamber_mask(db_session, chamber.id, mask_pn=mask.mask_pn)
    updated_chamber = settings_service.add_metalization_chamber_mask(db_session, chamber.id, mask_id=mask.id)

    assert [assigned.tool_pn for assigned in updated_machine.tools] == [tool.tool_pn]
    assert [assigned.mask_pn for assigned in updated_chamber.masks] == [mask.mask_pn]
