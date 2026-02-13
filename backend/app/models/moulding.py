from __future__ import annotations

from sqlalchemy import Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class MouldingMachineTool(Base):
    __tablename__ = "moulding_machine_tools"

    machine_id: Mapped[int] = mapped_column(
        ForeignKey("moulding_machines.id", ondelete="CASCADE"),
        primary_key=True,
    )
    tool_id: Mapped[int] = mapped_column(
        ForeignKey("moulding_tools.id", ondelete="CASCADE"),
        primary_key=True,
    )


class MouldingTool(Base):
    __tablename__ = "moulding_tools"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tool_pn: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    ct_seconds: Mapped[float] = mapped_column(Float, nullable=False)

    machines = relationship(
        "MouldingMachine",
        secondary="moulding_machine_tools",
        back_populates="tools",
        passive_deletes=True,
    )


class MouldingMachine(Base):
    __tablename__ = "moulding_machines"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    machine_number: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    tonnage: Mapped[int | None] = mapped_column(Integer, nullable=True)

    tools = relationship(
        "MouldingTool",
        secondary="moulding_machine_tools",
        back_populates="machines",
        passive_deletes=True,
    )
