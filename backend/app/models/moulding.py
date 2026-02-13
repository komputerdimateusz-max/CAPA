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


class ProjectMouldingTool(Base):
    __tablename__ = "project_moulding_tools"

    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"),
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

    hc_rows = relationship(
        "MouldingToolHC",
        back_populates="tool",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    machines = relationship(
        "MouldingMachine",
        secondary="moulding_machine_tools",
        back_populates="tools",
        passive_deletes=True,
    )
    projects = relationship(
        "Project",
        secondary="project_moulding_tools",
        back_populates="moulding_tools",
        passive_deletes=True,
    )
    material_rows = relationship(
        "MouldingToolMaterial",
        back_populates="tool",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    material_out_rows = relationship(
        "MouldingToolMaterialOut",
        back_populates="tool",
        cascade="all, delete-orphan",
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


class MouldingToolHC(Base):
    __tablename__ = "moulding_tool_hc"

    tool_id: Mapped[int] = mapped_column(
        ForeignKey("moulding_tools.id", ondelete="CASCADE"),
        primary_key=True,
    )
    worker_type: Mapped[str] = mapped_column(String(100), primary_key=True)
    hc: Mapped[float] = mapped_column(Float, nullable=False, default=0)

    tool = relationship("MouldingTool", back_populates="hc_rows")


class MouldingToolMaterial(Base):
    __tablename__ = "moulding_tool_materials"

    tool_id: Mapped[int] = mapped_column(
        ForeignKey("moulding_tools.id", ondelete="CASCADE"),
        primary_key=True,
    )
    material_id: Mapped[int] = mapped_column(
        ForeignKey("materials.id", ondelete="CASCADE"),
        primary_key=True,
    )
    qty_per_piece: Mapped[float] = mapped_column(Float, nullable=False)

    tool = relationship("MouldingTool", back_populates="material_rows")
    material = relationship("Material")


class MouldingToolMaterialOut(Base):
    __tablename__ = "moulding_tool_materials_out"

    tool_id: Mapped[int] = mapped_column(
        ForeignKey("moulding_tools.id", ondelete="CASCADE"),
        primary_key=True,
    )
    material_id: Mapped[int] = mapped_column(
        ForeignKey("materials.id", ondelete="CASCADE"),
        primary_key=True,
    )
    qty_per_piece: Mapped[float] = mapped_column(Float, nullable=False)

    tool = relationship("MouldingTool", back_populates="material_out_rows")
    material = relationship("Material")
