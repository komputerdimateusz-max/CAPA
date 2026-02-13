from __future__ import annotations

from sqlalchemy import delete, select
from sqlalchemy.orm import Session, selectinload

from app.models.moulding import MouldingMachine, MouldingTool, MouldingToolHC


def list_moulding_tools(db: Session) -> list[MouldingTool]:
    stmt = (
        select(MouldingTool)
        .options(selectinload(MouldingTool.hc_rows))
        .order_by(MouldingTool.tool_pn.asc())
    )
    return list(db.scalars(stmt).all())


def get_moulding_tool(db: Session, tool_id: int) -> MouldingTool | None:
    stmt = (
        select(MouldingTool)
        .options(selectinload(MouldingTool.hc_rows))
        .where(MouldingTool.id == tool_id)
    )
    return db.scalar(stmt)


def get_tool_hc_map(db: Session, tool_id: int) -> dict[str, float]:
    stmt = select(MouldingToolHC).where(MouldingToolHC.tool_id == tool_id)
    return {row.worker_type: row.hc for row in db.scalars(stmt).all()}


def set_tool_hc(db: Session, tool_id: int, hc_map: dict[str, float]) -> None:
    db.execute(delete(MouldingToolHC).where(MouldingToolHC.tool_id == tool_id))
    for worker_type, hc in hc_map.items():
        db.add(MouldingToolHC(tool_id=tool_id, worker_type=worker_type, hc=hc))


def create_moulding_tool(db: Session, *, tool_pn: str, description: str | None, ct_seconds: float) -> MouldingTool:
    tool = MouldingTool(tool_pn=tool_pn, description=description, ct_seconds=ct_seconds)
    db.add(tool)
    db.commit()
    db.refresh(tool)
    return tool


def update_moulding_tool(
    db: Session,
    *,
    tool: MouldingTool,
    tool_pn: str,
    description: str | None,
    ct_seconds: float,
) -> MouldingTool:
    tool.tool_pn = tool_pn
    tool.description = description
    tool.ct_seconds = ct_seconds
    db.add(tool)
    db.commit()
    db.refresh(tool)
    return tool


def delete_moulding_tool(db: Session, *, tool: MouldingTool) -> None:
    db.delete(tool)
    db.commit()


def list_moulding_machines(db: Session) -> list[MouldingMachine]:
    stmt = (
        select(MouldingMachine)
        .options(selectinload(MouldingMachine.tools))
        .order_by(MouldingMachine.machine_number.asc())
    )
    return list(db.scalars(stmt).all())


def get_moulding_machine(db: Session, machine_id: int) -> MouldingMachine | None:
    stmt = (
        select(MouldingMachine)
        .options(selectinload(MouldingMachine.tools))
        .where(MouldingMachine.id == machine_id)
    )
    return db.scalar(stmt)


def list_tools_for_machine(db: Session, machine_id: int) -> list[MouldingTool]:
    stmt = (
        select(MouldingTool)
        .join(MouldingMachine.tools)
        .where(MouldingMachine.id == machine_id)
        .order_by(MouldingTool.tool_pn.asc())
    )
    return list(db.scalars(stmt).all())


def create_moulding_machine(
    db: Session,
    *,
    machine_number: str,
    tonnage: int | None,
    tools: list[MouldingTool],
) -> MouldingMachine:
    machine = MouldingMachine(machine_number=machine_number, tonnage=tonnage)
    machine.tools = tools
    db.add(machine)
    db.commit()
    db.refresh(machine)
    return machine


def update_moulding_machine(
    db: Session,
    *,
    machine: MouldingMachine,
    machine_number: str,
    tonnage: int | None,
    tools: list[MouldingTool],
) -> MouldingMachine:
    machine.machine_number = machine_number
    machine.tonnage = tonnage
    machine.tools = tools
    db.add(machine)
    db.commit()
    db.refresh(machine)
    return machine


def delete_moulding_machine(db: Session, *, machine: MouldingMachine) -> None:
    db.delete(machine)
    db.commit()
