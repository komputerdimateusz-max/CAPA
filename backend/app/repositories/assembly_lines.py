from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.assembly_line import AssemblyLine


def list_assembly_lines(db: Session) -> list[AssemblyLine]:
    stmt = select(AssemblyLine).order_by(AssemblyLine.line_number.asc())
    return list(db.scalars(stmt).all())


def get_assembly_line(db: Session, assembly_line_id: int) -> AssemblyLine | None:
    return db.get(AssemblyLine, assembly_line_id)


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
