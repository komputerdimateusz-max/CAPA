from __future__ import annotations

from sqlalchemy import case, select
from sqlalchemy.orm import Session

from app.models.labour_cost import LabourCost


def list_labour_costs(db: Session, ordered_types: tuple[str, ...]) -> list[LabourCost]:
    order_map = {worker_type: index for index, worker_type in enumerate(ordered_types)}
    ordering = case(order_map, value=LabourCost.worker_type)
    stmt = select(LabourCost).order_by(ordering.asc())
    return list(db.scalars(stmt).all())


def get_by_worker_type(db: Session, worker_type: str) -> LabourCost | None:
    stmt = select(LabourCost).where(LabourCost.worker_type == worker_type)
    return db.scalar(stmt)


def create_labour_cost(db: Session, worker_type: str, cost_pln: float = 0) -> LabourCost:
    labour_cost = LabourCost(worker_type=worker_type, cost_pln=cost_pln)
    db.add(labour_cost)
    db.commit()
    db.refresh(labour_cost)
    return labour_cost


def update_labour_cost(db: Session, labour_cost: LabourCost, cost_pln: float) -> LabourCost:
    labour_cost.cost_pln = cost_pln
    db.add(labour_cost)
    db.commit()
    db.refresh(labour_cost)
    return labour_cost
