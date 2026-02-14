from __future__ import annotations

from datetime import date

from sqlalchemy import Column, Date, ForeignKey, String, Table, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.tag import analysis_tags


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
