from __future__ import annotations

from sqlalchemy import Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class ProjectAssemblyLine(Base):
    __tablename__ = "project_assembly_lines"

    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"),
        primary_key=True,
    )
    line_id: Mapped[int] = mapped_column(
        ForeignKey("assembly_lines.id", ondelete="CASCADE"),
        primary_key=True,
    )


class AssemblyLine(Base):
    __tablename__ = "assembly_lines"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    line_number: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    ct_seconds: Mapped[float] = mapped_column(Float, nullable=False)
    hc: Mapped[int] = mapped_column(Integer, nullable=False)

    projects = relationship(
        "Project",
        secondary="project_assembly_lines",
        back_populates="assembly_lines",
        passive_deletes=True,
    )
    hc_rows = relationship(
        "AssemblyLineHC",
        back_populates="line",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    material_in_rows = relationship(
        "AssemblyLineMaterialIn",
        back_populates="line",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    material_out_rows = relationship(
        "AssemblyLineMaterialOut",
        back_populates="line",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class AssemblyLineHC(Base):
    __tablename__ = "assembly_line_hc"

    line_id: Mapped[int] = mapped_column(
        ForeignKey("assembly_lines.id", ondelete="CASCADE"),
        primary_key=True,
    )
    worker_type: Mapped[str] = mapped_column(String(100), primary_key=True)
    hc: Mapped[float] = mapped_column(Float, nullable=False, default=0)

    line = relationship("AssemblyLine", back_populates="hc_rows")


class AssemblyLineMaterialIn(Base):
    __tablename__ = "assembly_line_materials_in"

    line_id: Mapped[int] = mapped_column(
        ForeignKey("assembly_lines.id", ondelete="CASCADE"),
        primary_key=True,
    )
    material_id: Mapped[int] = mapped_column(
        ForeignKey("materials.id", ondelete="CASCADE"),
        primary_key=True,
    )
    qty_per_piece: Mapped[float] = mapped_column(Float, nullable=False)

    line = relationship("AssemblyLine", back_populates="material_in_rows")
    material = relationship("Material")


class AssemblyLineMaterialOut(Base):
    __tablename__ = "assembly_line_materials_out"

    line_id: Mapped[int] = mapped_column(
        ForeignKey("assembly_lines.id", ondelete="CASCADE"),
        primary_key=True,
    )
    material_id: Mapped[int] = mapped_column(
        ForeignKey("materials.id", ondelete="CASCADE"),
        primary_key=True,
    )
    qty_per_piece: Mapped[float] = mapped_column(Float, nullable=False)

    line = relationship("AssemblyLine", back_populates="material_out_rows")
    material = relationship("Material")
