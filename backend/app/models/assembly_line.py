from __future__ import annotations

from sqlalchemy import Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class AssemblyLine(Base):
    __tablename__ = "assembly_lines"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    line_number: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    ct_seconds: Mapped[float] = mapped_column(Float, nullable=False)
    hc: Mapped[int] = mapped_column(Integer, nullable=False)
