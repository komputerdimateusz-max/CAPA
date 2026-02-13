from __future__ import annotations

from sqlalchemy import Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class LabourCost(Base):
    __tablename__ = "labour_costs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    worker_type: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    cost_pln: Mapped[float] = mapped_column(Float, nullable=False, default=0)
