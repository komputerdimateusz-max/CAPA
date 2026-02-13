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
