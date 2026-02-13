from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.material import Material


def list_materials(db: Session) -> list[Material]:
    stmt = select(Material).order_by(Material.part_number.asc())
    return list(db.scalars(stmt).all())


def get_material(db: Session, material_id: int) -> Material | None:
    return db.get(Material, material_id)


def create_material(
    db: Session,
    *,
    part_number: str,
    description: str | None,
    unit: str,
    price_per_unit: float,
    category: str,
    make_buy: bool,
) -> Material:
    material = Material(
        part_number=part_number,
        description=description,
        unit=unit,
        price_per_unit=price_per_unit,
        category=category,
        make_buy=make_buy,
    )
    db.add(material)
    db.commit()
    db.refresh(material)
    return material


def update_material(
    db: Session,
    *,
    material: Material,
    part_number: str,
    description: str | None,
    unit: str,
    price_per_unit: float,
    category: str,
    make_buy: bool,
) -> Material:
    material.part_number = part_number
    material.description = description
    material.unit = unit
    material.price_per_unit = price_per_unit
    material.category = category
    material.make_buy = make_buy
    db.add(material)
    db.commit()
    db.refresh(material)
    return material


def delete_material(db: Session, *, material: Material) -> None:
    db.delete(material)
    db.commit()
