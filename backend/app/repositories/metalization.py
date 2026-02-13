from __future__ import annotations

from sqlalchemy import delete, select
from sqlalchemy.orm import Session, selectinload

from app.models.metalization import MetalizationChamber, MetalizationMask, MetalizationMaskHC, MetalizationMaskMaterial


def list_metalization_masks(db: Session) -> list[MetalizationMask]:
    stmt = (
        select(MetalizationMask)
        .options(selectinload(MetalizationMask.hc_rows), selectinload(MetalizationMask.material_rows).selectinload(MetalizationMaskMaterial.material))
        .order_by(MetalizationMask.mask_pn.asc())
    )
    return list(db.scalars(stmt).all())


def get_metalization_mask(db: Session, mask_id: int) -> MetalizationMask | None:
    stmt = (
        select(MetalizationMask)
        .options(selectinload(MetalizationMask.hc_rows), selectinload(MetalizationMask.material_rows).selectinload(MetalizationMaskMaterial.material))
        .where(MetalizationMask.id == mask_id)
    )
    return db.scalar(stmt)


def get_mask_hc_map(db: Session, mask_id: int) -> dict[str, float]:
    stmt = select(MetalizationMaskHC).where(MetalizationMaskHC.mask_id == mask_id)
    return {row.worker_type: row.hc for row in db.scalars(stmt).all()}


def set_mask_hc(db: Session, mask_id: int, hc_map: dict[str, float]) -> None:
    db.execute(delete(MetalizationMaskHC).where(MetalizationMaskHC.mask_id == mask_id))
    for worker_type, hc in hc_map.items():
        db.add(MetalizationMaskHC(mask_id=mask_id, worker_type=worker_type, hc=hc))


def create_metalization_mask(db: Session, *, mask_pn: str, description: str | None, ct_seconds: float) -> MetalizationMask:
    mask = MetalizationMask(mask_pn=mask_pn, description=description, ct_seconds=ct_seconds)
    db.add(mask)
    db.commit()
    db.refresh(mask)
    return mask


def update_metalization_mask(
    db: Session,
    *,
    mask: MetalizationMask,
    mask_pn: str,
    description: str | None,
    ct_seconds: float,
) -> MetalizationMask:
    mask.mask_pn = mask_pn
    mask.description = description
    mask.ct_seconds = ct_seconds
    db.add(mask)
    db.commit()
    db.refresh(mask)
    return mask


def delete_metalization_mask(db: Session, *, mask: MetalizationMask) -> None:
    db.delete(mask)
    db.commit()


def list_materials_for_mask(db: Session, mask_id: int) -> list[MetalizationMaskMaterial]:
    stmt = (
        select(MetalizationMaskMaterial)
        .options(selectinload(MetalizationMaskMaterial.material))
        .where(MetalizationMaskMaterial.mask_id == mask_id)
        .order_by(MetalizationMaskMaterial.material_id.asc())
    )
    return list(db.scalars(stmt).all())


def get_mask_material(db: Session, mask_id: int, material_id: int) -> MetalizationMaskMaterial | None:
    stmt = select(MetalizationMaskMaterial).where(
        MetalizationMaskMaterial.mask_id == mask_id,
        MetalizationMaskMaterial.material_id == material_id,
    )
    return db.scalar(stmt)


def upsert_mask_material(db: Session, *, mask_id: int, material_id: int, qty_per_piece: float) -> MetalizationMaskMaterial:
    row = get_mask_material(db, mask_id, material_id)
    if row is None:
        row = MetalizationMaskMaterial(mask_id=mask_id, material_id=material_id, qty_per_piece=qty_per_piece)
    else:
        row.qty_per_piece = qty_per_piece
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def delete_mask_material(db: Session, *, mask_id: int, material_id: int) -> None:
    row = get_mask_material(db, mask_id, material_id)
    if row is None:
        return
    db.delete(row)
    db.commit()


def list_metalization_chambers(db: Session) -> list[MetalizationChamber]:
    stmt = (
        select(MetalizationChamber)
        .options(selectinload(MetalizationChamber.masks))
        .order_by(MetalizationChamber.chamber_number.asc())
    )
    return list(db.scalars(stmt).all())


def get_metalization_chamber(db: Session, chamber_id: int) -> MetalizationChamber | None:
    stmt = (
        select(MetalizationChamber)
        .options(selectinload(MetalizationChamber.masks))
        .where(MetalizationChamber.id == chamber_id)
    )
    return db.scalar(stmt)


def create_metalization_chamber(
    db: Session,
    *,
    chamber_number: str,
    masks: list[MetalizationMask],
) -> MetalizationChamber:
    chamber = MetalizationChamber(chamber_number=chamber_number)
    chamber.masks = masks
    db.add(chamber)
    db.commit()
    db.refresh(chamber)
    return chamber


def update_metalization_chamber(
    db: Session,
    *,
    chamber: MetalizationChamber,
    chamber_number: str,
    masks: list[MetalizationMask],
) -> MetalizationChamber:
    chamber.chamber_number = chamber_number
    chamber.masks = masks
    db.add(chamber)
    db.commit()
    db.refresh(chamber)
    return chamber


def delete_metalization_chamber(db: Session, *, chamber: MetalizationChamber) -> None:
    db.delete(chamber)
    db.commit()
