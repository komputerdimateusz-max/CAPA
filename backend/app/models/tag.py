from __future__ import annotations

from sqlalchemy import Column, ForeignKey, Integer, String, Table
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


action_tags = Table(
    "action_tags",
    Base.metadata,
    Column("action_id", ForeignKey("actions.id", ondelete="CASCADE"), primary_key=True),
    Column("tag_id", ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True),
)

analysis_tags = Table(
    "analysis_tags",
    Base.metadata,
    Column("analysis_id", ForeignKey("analyses.id", ondelete="CASCADE"), primary_key=True),
    Column("tag_id", ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True),
)


class Tag(Base):
    __tablename__ = "tags"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    color: Mapped[str | None] = mapped_column(String(32), nullable=True)

    actions = relationship("Action", secondary=action_tags, back_populates="tags")
    analyses = relationship("Analysis", secondary=analysis_tags, back_populates="tags")
