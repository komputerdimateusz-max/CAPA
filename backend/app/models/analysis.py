from __future__ import annotations

from datetime import date

from sqlalchemy import Column, Date, ForeignKey, String, Table, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.tag import analysis_tags

OBSERVED_PROCESS_TYPE_MOULDING = "moulding"
OBSERVED_PROCESS_TYPE_METALIZATION = "metalization"
OBSERVED_PROCESS_TYPE_ASSEMBLY = "assembly"
ALLOWED_OBSERVED_PROCESS_TYPES = (
    OBSERVED_PROCESS_TYPE_MOULDING,
    OBSERVED_PROCESS_TYPE_METALIZATION,
    OBSERVED_PROCESS_TYPE_ASSEMBLY,
)


class Analysis(Base):
    __tablename__ = "analyses"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    type: Mapped[str] = mapped_column(String(20), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=True, default="")
    champion: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="Open")
    created_at: Mapped[date] = mapped_column(Date, nullable=False)
    closed_at: Mapped[date | None] = mapped_column(Date, nullable=True)

    tags = relationship("Tag", secondary=analysis_tags, back_populates="analyses")
    details_5why = relationship(
        "Analysis5Why",
        back_populates="analysis",
        cascade="all, delete-orphan",
        uselist=False,
    )
    actions = relationship("Action", secondary="analysis_actions", back_populates="analyses")


analysis_actions = Table(
    "analysis_actions",
    Base.metadata,
    Column("analysis_id", ForeignKey("analyses.id", ondelete="CASCADE"), primary_key=True),
    Column("action_id", ForeignKey("actions.id", ondelete="CASCADE"), primary_key=True),
)


class Analysis5Why(Base):
    __tablename__ = "analysis_5why"

    analysis_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("analyses.id", ondelete="CASCADE"),
        primary_key=True,
    )
    problem_statement: Mapped[str] = mapped_column(Text, nullable=False)
    where_observed: Mapped[str | None] = mapped_column(Text, nullable=True)
    observed_process_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    date_detected: Mapped[date | None] = mapped_column(Date, nullable=True)
    why_1: Mapped[str | None] = mapped_column(Text, nullable=True)
    why_2: Mapped[str | None] = mapped_column(Text, nullable=True)
    why_3: Mapped[str | None] = mapped_column(Text, nullable=True)
    why_4: Mapped[str | None] = mapped_column(Text, nullable=True)
    why_5: Mapped[str | None] = mapped_column(Text, nullable=True)
    root_cause: Mapped[str] = mapped_column(Text, nullable=False)
    root_cause_category: Mapped[str | None] = mapped_column(String(32), nullable=True)
    containment_action: Mapped[str | None] = mapped_column(Text, nullable=True)
    proposed_action: Mapped[str | None] = mapped_column(Text, nullable=True)

    analysis = relationship("Analysis", back_populates="details_5why")
    moulding_tools = relationship(
        "MouldingTool",
        secondary="analysis_5why_moulding_tools",
        passive_deletes=True,
    )
    metalization_masks = relationship(
        "MetalizationMask",
        secondary="analysis_5why_metalization_masks",
        passive_deletes=True,
    )
    assembly_references = relationship(
        "AssemblyLineReference",
        secondary="analysis_5why_assembly_references",
        passive_deletes=True,
    )


class Analysis5WhyMouldingTool(Base):
    __tablename__ = "analysis_5why_moulding_tools"

    analysis_id: Mapped[str] = mapped_column(
        ForeignKey("analyses.id", ondelete="CASCADE"),
        primary_key=True,
    )
    tool_id: Mapped[int] = mapped_column(
        ForeignKey("moulding_tools.id", ondelete="CASCADE"),
        primary_key=True,
    )


class Analysis5WhyMetalizationMask(Base):
    __tablename__ = "analysis_5why_metalization_masks"

    analysis_id: Mapped[str] = mapped_column(
        ForeignKey("analyses.id", ondelete="CASCADE"),
        primary_key=True,
    )
    mask_id: Mapped[int] = mapped_column(
        ForeignKey("metalization_masks.id", ondelete="CASCADE"),
        primary_key=True,
    )


class Analysis5WhyAssemblyReference(Base):
    __tablename__ = "analysis_5why_assembly_references"

    analysis_id: Mapped[str] = mapped_column(
        ForeignKey("analyses.id", ondelete="CASCADE"),
        primary_key=True,
    )
    reference_id: Mapped[int] = mapped_column(
        ForeignKey("assembly_line_references.id", ondelete="CASCADE"),
        primary_key=True,
    )
