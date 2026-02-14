from __future__ import annotations

from datetime import datetime, date

from sqlalchemy import Date, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.tag import action_tags

PROCESS_TYPE_MOULDING = "moulding"
PROCESS_TYPE_METALIZATION = "metalization"
PROCESS_TYPE_ASSEMBLY = "assembly"
ALLOWED_PROCESS_TYPES = (PROCESS_TYPE_MOULDING, PROCESS_TYPE_METALIZATION, PROCESS_TYPE_ASSEMBLY)


class ActionMouldingTool(Base):
    __tablename__ = "action_moulding_tools"

    action_id: Mapped[int] = mapped_column(
        ForeignKey("actions.id", ondelete="CASCADE"),
        primary_key=True,
    )
    tool_id: Mapped[int] = mapped_column(
        ForeignKey("moulding_tools.id", ondelete="CASCADE"),
        primary_key=True,
    )


class ActionMetalizationMask(Base):
    __tablename__ = "action_metalization_masks"

    action_id: Mapped[int] = mapped_column(
        ForeignKey("actions.id", ondelete="CASCADE"),
        primary_key=True,
    )
    mask_id: Mapped[int] = mapped_column(
        ForeignKey("metalization_masks.id", ondelete="CASCADE"),
        primary_key=True,
    )


class ActionAssemblyReference(Base):
    __tablename__ = "action_assembly_references"

    action_id: Mapped[int] = mapped_column(
        ForeignKey("actions.id", ondelete="CASCADE"),
        primary_key=True,
    )
    reference_id: Mapped[int] = mapped_column(
        ForeignKey("assembly_line_references.id", ondelete="CASCADE"),
        primary_key=True,
    )


class Action(Base):
    __tablename__ = "actions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=True, default="")
    project_id: Mapped[int | None] = mapped_column(ForeignKey("projects.id"), nullable=True)
    champion_id: Mapped[int | None] = mapped_column(ForeignKey("champions.id"), nullable=True)
    owner: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="OPEN")
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    priority: Mapped[str | None] = mapped_column(String(50), nullable=True)
    process_type: Mapped[str | None] = mapped_column(String(32), nullable=True)

    project = relationship("Project", back_populates="actions")
    champion = relationship("Champion", back_populates="actions")
    tags = relationship("Tag", secondary=action_tags, back_populates="actions")
    subtasks = relationship(
        "Subtask",
        back_populates="action",
        cascade="all, delete-orphan",
    )
    moulding_tools = relationship(
        "MouldingTool",
        secondary="action_moulding_tools",
        passive_deletes=True,
    )
    metalization_masks = relationship(
        "MetalizationMask",
        secondary="action_metalization_masks",
        passive_deletes=True,
    )
    assembly_references = relationship(
        "AssemblyLineReference",
        secondary="action_assembly_references",
        passive_deletes=True,
    )
