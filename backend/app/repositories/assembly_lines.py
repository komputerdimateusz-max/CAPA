from __future__ import annotations

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session, selectinload

from app.models.assembly_line import (
    AssemblyLine,
    AssemblyLineHC,
    AssemblyLineMaterialIn,
    AssemblyLineMaterialOut,
)
from app.models.material import Material


def list_assembly_lines(db: Session) -> list[AssemblyLine]:
    stmt = (
        select(AssemblyLine)
        .options(
            selectinload(AssemblyLine.hc_rows),
            selectinload(AssemblyLine.material_in_rows).selectinload(AssemblyLineMaterialIn.material),
            selectinload(AssemblyLine.material_out_rows).selectinload(AssemblyLineMaterialOut.material),
        )
        .order_by(AssemblyLine.line_number.asc())
    )
    return list(db.scalars(stmt).all())


def get_assembly_line(db: Session, assembly_line_id: int) -> AssemblyLine | None:
    stmt = (
        select(AssemblyLine)
        .options(
            selectinload(AssemblyLine.hc_rows),
            selectinload(AssemblyLine.material_in_rows).selectinload(AssemblyLineMaterialIn.material),
            selectinload(AssemblyLine.material_out_rows).selectinload(AssemblyLineMaterialOut.material),
        )
        .where(AssemblyLine.id == assembly_line_id)
    )
    return db.scalar(stmt)


def create_assembly_line(db: Session, *, line_number: str, ct_seconds: float, hc: int) -> AssemblyLine:
    assembly_line = AssemblyLine(line_number=line_number, ct_seconds=ct_seconds, hc=hc)
    db.add(assembly_line)
    db.commit()
    db.refresh(assembly_line)
    return assembly_line


def update_assembly_line(
    db: Session,
    *,
    assembly_line: AssemblyLine,
    line_number: str,
    ct_seconds: float,
    hc: int,
) -> AssemblyLine:
    assembly_line.line_number = line_number
    assembly_line.ct_seconds = ct_seconds
    assembly_line.hc = hc
    db.add(assembly_line)
    db.commit()
    db.refresh(assembly_line)
    return assembly_line


def delete_assembly_line(db: Session, *, assembly_line: AssemblyLine) -> None:
    db.delete(assembly_line)
    db.commit()


def get_line_hc_map(db: Session, line_id: int) -> dict[str, float]:
    stmt = select(AssemblyLineHC).where(AssemblyLineHC.line_id == line_id)
    return {row.worker_type: row.hc for row in db.scalars(stmt).all()}


def set_line_hc(db: Session, line_id: int, hc_map: dict[str, float]) -> None:
    db.execute(delete(AssemblyLineHC).where(AssemblyLineHC.line_id == line_id))
    for worker_type, hc in hc_map.items():
        db.add(AssemblyLineHC(line_id=line_id, worker_type=worker_type, hc=hc))


def list_materials_in_for_line(db: Session, line_id: int) -> list[AssemblyLineMaterialIn]:
    stmt = (
        select(AssemblyLineMaterialIn)
        .options(selectinload(AssemblyLineMaterialIn.material))
        .where(AssemblyLineMaterialIn.line_id == line_id)
        .order_by(AssemblyLineMaterialIn.material_id.asc())
    )
    return list(db.scalars(stmt).all())


def list_materials_out_for_line(db: Session, line_id: int) -> list[AssemblyLineMaterialOut]:
    stmt = (
        select(AssemblyLineMaterialOut)
        .options(selectinload(AssemblyLineMaterialOut.material))
        .where(AssemblyLineMaterialOut.line_id == line_id)
        .order_by(AssemblyLineMaterialOut.material_id.asc())
    )
    return list(db.scalars(stmt).all())


def get_line_material_in(db: Session, line_id: int, material_id: int) -> AssemblyLineMaterialIn | None:
    stmt = select(AssemblyLineMaterialIn).where(
        AssemblyLineMaterialIn.line_id == line_id,
        AssemblyLineMaterialIn.material_id == material_id,
    )
    return db.scalar(stmt)


def get_line_material_out(db: Session, line_id: int, material_id: int) -> AssemblyLineMaterialOut | None:
    stmt = select(AssemblyLineMaterialOut).where(
        AssemblyLineMaterialOut.line_id == line_id,
        AssemblyLineMaterialOut.material_id == material_id,
    )
    return db.scalar(stmt)


def upsert_line_material_in(db: Session, *, line_id: int, material_id: int, qty_per_piece: float) -> AssemblyLineMaterialIn:
    row = get_line_material_in(db, line_id, material_id)
    if row is None:
        row = AssemblyLineMaterialIn(line_id=line_id, material_id=material_id, qty_per_piece=qty_per_piece)
    else:
        row.qty_per_piece = qty_per_piece
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def upsert_line_material_out(db: Session, *, line_id: int, material_id: int, qty_per_piece: float) -> AssemblyLineMaterialOut:
    row = get_line_material_out(db, line_id, material_id)
    if row is None:
        row = AssemblyLineMaterialOut(line_id=line_id, material_id=material_id, qty_per_piece=qty_per_piece)
    else:
        row.qty_per_piece = qty_per_piece
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def delete_line_material_in(db: Session, *, line_id: int, material_id: int) -> None:
    row = get_line_material_in(db, line_id, material_id)
    if row is None:
        return
    db.delete(row)
    db.commit()


def delete_line_material_out(db: Session, *, line_id: int, material_id: int) -> None:
    row = get_line_material_out(db, line_id, material_id)
    if row is None:
        return
    db.delete(row)
    db.commit()


def _material_cost_map(db: Session, model) -> dict[int, float]:
    stmt = (
        select(
            model.line_id,
            func.coalesce(func.sum(model.qty_per_piece * Material.price_per_unit), 0.0),
        )
        .join(Material, Material.id == model.material_id)
        .group_by(model.line_id)
    )
    return {line_id: float(total or 0.0) for line_id, total in db.execute(stmt).all()}


def material_in_cost_map_for_lines(db: Session) -> dict[int, float]:
    return _material_cost_map(db, AssemblyLineMaterialIn)


def material_out_cost_map_for_lines(db: Session) -> dict[int, float]:
    return _material_cost_map(db, AssemblyLineMaterialOut)
