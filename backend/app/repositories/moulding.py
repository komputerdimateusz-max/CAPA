from __future__ import annotations

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session, selectinload

from app.models.material import Material
from app.models.moulding import (
    MouldingMachine,
    MouldingTool,
    MouldingToolHC,
    MouldingToolMaterial,
    MouldingToolMaterialOut,
)


def list_moulding_tools(db: Session) -> list[MouldingTool]:
    stmt = (
        select(MouldingTool)
        .options(
            selectinload(MouldingTool.hc_rows),
            selectinload(MouldingTool.material_rows).selectinload(MouldingToolMaterial.material),
            selectinload(MouldingTool.material_out_rows).selectinload(MouldingToolMaterialOut.material),
        )
        .order_by(MouldingTool.tool_pn.asc())
    )
    return list(db.scalars(stmt).all())


def get_moulding_tool(db: Session, tool_id: int) -> MouldingTool | None:
    stmt = (
        select(MouldingTool)
        .options(
            selectinload(MouldingTool.hc_rows),
            selectinload(MouldingTool.material_rows).selectinload(MouldingToolMaterial.material),
            selectinload(MouldingTool.material_out_rows).selectinload(MouldingToolMaterialOut.material),
        )
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


def list_materials_for_tool(db: Session, tool_id: int) -> list[MouldingToolMaterial]:
    stmt = (
        select(MouldingToolMaterial)
        .options(selectinload(MouldingToolMaterial.material))
        .where(MouldingToolMaterial.tool_id == tool_id)
        .order_by(MouldingToolMaterial.material_id.asc())
    )
    return list(db.scalars(stmt).all())


def list_materials_out_for_tool(db: Session, tool_id: int) -> list[MouldingToolMaterialOut]:
    stmt = (
        select(MouldingToolMaterialOut)
        .options(selectinload(MouldingToolMaterialOut.material))
        .where(MouldingToolMaterialOut.tool_id == tool_id)
        .order_by(MouldingToolMaterialOut.material_id.asc())
    )
    return list(db.scalars(stmt).all())


def _material_cost_map(db: Session, model) -> dict[int, float]:
    stmt = (
        select(
            model.tool_id,
            func.coalesce(func.sum(model.qty_per_piece * Material.price_per_unit), 0.0),
        )
        .join(Material, Material.id == model.material_id)
        .group_by(model.tool_id)
    )
    return {tool_id: float(total or 0.0) for tool_id, total in db.execute(stmt).all()}


def material_cost_map_for_tools(db: Session) -> dict[int, float]:
    return _material_cost_map(db, MouldingToolMaterial)


def material_out_cost_map_for_tools(db: Session) -> dict[int, float]:
    return _material_cost_map(db, MouldingToolMaterialOut)


def _compute_material_cost(db: Session, tool_id: int, model) -> float:
    stmt = (
        select(func.coalesce(func.sum(model.qty_per_piece * Material.price_per_unit), 0.0))
        .join(Material, Material.id == model.material_id)
        .where(model.tool_id == tool_id)
    )
    return float(db.scalar(stmt) or 0.0)


def compute_material_cost_for_tool(db: Session, tool_id: int) -> float:
    return _compute_material_cost(db, tool_id, MouldingToolMaterial)


def compute_material_out_cost_for_tool(db: Session, tool_id: int) -> float:
    return _compute_material_cost(db, tool_id, MouldingToolMaterialOut)


def get_tool_material(db: Session, tool_id: int, material_id: int) -> MouldingToolMaterial | None:
    stmt = select(MouldingToolMaterial).where(
        MouldingToolMaterial.tool_id == tool_id,
        MouldingToolMaterial.material_id == material_id,
    )
    return db.scalar(stmt)


def get_tool_material_out(db: Session, tool_id: int, material_id: int) -> MouldingToolMaterialOut | None:
    stmt = select(MouldingToolMaterialOut).where(
        MouldingToolMaterialOut.tool_id == tool_id,
        MouldingToolMaterialOut.material_id == material_id,
    )
    return db.scalar(stmt)


def upsert_tool_material(db: Session, *, tool_id: int, material_id: int, qty_per_piece: float) -> MouldingToolMaterial:
    row = get_tool_material(db, tool_id, material_id)
    if row is None:
        row = MouldingToolMaterial(tool_id=tool_id, material_id=material_id, qty_per_piece=qty_per_piece)
    else:
        row.qty_per_piece = qty_per_piece
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def upsert_tool_material_out(db: Session, *, tool_id: int, material_id: int, qty_per_piece: float) -> MouldingToolMaterialOut:
    row = get_tool_material_out(db, tool_id, material_id)
    if row is None:
        row = MouldingToolMaterialOut(tool_id=tool_id, material_id=material_id, qty_per_piece=qty_per_piece)
    else:
        row.qty_per_piece = qty_per_piece
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def delete_tool_material(db: Session, *, tool_id: int, material_id: int) -> None:
    row = get_tool_material(db, tool_id, material_id)
    if row is None:
        return
    db.delete(row)
    db.commit()


def delete_tool_material_out(db: Session, *, tool_id: int, material_id: int) -> None:
    row = get_tool_material_out(db, tool_id, material_id)
    if row is None:
        return
    db.delete(row)
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
