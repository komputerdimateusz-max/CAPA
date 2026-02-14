from __future__ import annotations

from datetime import date

from sqlalchemy import Date, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str | None] = mapped_column(String(50), nullable=True)
    max_volume: Mapped[int | None] = mapped_column(Integer, nullable=True)
    flex_percent: Mapped[float | None] = mapped_column(Float, nullable=True)
    process_engineer_id: Mapped[int | None] = mapped_column(
        ForeignKey("champions.id", ondelete="SET NULL"),
        nullable=True,
    )

    actions = relationship("Action", back_populates="project")
    process_engineer = relationship("Champion", back_populates="process_engineer_projects")
    moulding_tools = relationship(
        "MouldingTool",
        secondary="project_moulding_tools",
        back_populates="projects",
        passive_deletes=True,
    )
    assembly_lines = relationship(
        "AssemblyLine",
        secondary="project_assembly_lines",
        back_populates="projects",
        passive_deletes=True,
    )
    metalization_masks = relationship(
        "MetalizationMask",
        secondary="project_metalization_masks",
        back_populates="projects",
        passive_deletes=True,
    )
