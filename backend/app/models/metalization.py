from __future__ import annotations

from sqlalchemy import Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class MetalizationChamberMask(Base):
    __tablename__ = "metalization_chamber_masks"

    chamber_id: Mapped[int] = mapped_column(
        ForeignKey("metalization_chambers.id", ondelete="CASCADE"),
        primary_key=True,
    )
    mask_id: Mapped[int] = mapped_column(
        ForeignKey("metalization_masks.id", ondelete="CASCADE"),
        primary_key=True,
    )


class ProjectMetalizationMask(Base):
    __tablename__ = "project_metalization_masks"

    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"),
        primary_key=True,
    )
    mask_id: Mapped[int] = mapped_column(
        ForeignKey("metalization_masks.id", ondelete="CASCADE"),
        primary_key=True,
    )


class MetalizationMask(Base):
    __tablename__ = "metalization_masks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    mask_pn: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    ct_seconds: Mapped[float] = mapped_column(Float, nullable=False)

    hc_rows = relationship(
        "MetalizationMaskHC",
        back_populates="mask",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    chambers = relationship(
        "MetalizationChamber",
        secondary="metalization_chamber_masks",
        back_populates="masks",
        passive_deletes=True,
    )
    projects = relationship(
        "Project",
        secondary="project_metalization_masks",
        back_populates="metalization_masks",
        passive_deletes=True,
    )
    material_rows = relationship(
        "MetalizationMaskMaterial",
        back_populates="mask",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    material_out_rows = relationship(
        "MetalizationMaskMaterialOut",
        back_populates="mask",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class MetalizationChamber(Base):
    __tablename__ = "metalization_chambers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    chamber_number: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)

    masks = relationship(
        "MetalizationMask",
        secondary="metalization_chamber_masks",
        back_populates="chambers",
        passive_deletes=True,
    )


class MetalizationMaskHC(Base):
    __tablename__ = "metalization_mask_hc"

    mask_id: Mapped[int] = mapped_column(
        ForeignKey("metalization_masks.id", ondelete="CASCADE"),
        primary_key=True,
    )
    worker_type: Mapped[str] = mapped_column(String(100), primary_key=True)
    hc: Mapped[float] = mapped_column(Float, nullable=False, default=0)

    mask = relationship("MetalizationMask", back_populates="hc_rows")


class MetalizationMaskMaterial(Base):
    __tablename__ = "metalization_mask_materials"

    mask_id: Mapped[int] = mapped_column(
        ForeignKey("metalization_masks.id", ondelete="CASCADE"),
        primary_key=True,
    )
    material_id: Mapped[int] = mapped_column(
        ForeignKey("materials.id", ondelete="CASCADE"),
        primary_key=True,
    )
    qty_per_piece: Mapped[float] = mapped_column(Float, nullable=False)

    mask = relationship("MetalizationMask", back_populates="material_rows")
    material = relationship("Material")


class MetalizationMaskMaterialOut(Base):
    __tablename__ = "metalization_mask_materials_out"

    mask_id: Mapped[int] = mapped_column(
        ForeignKey("metalization_masks.id", ondelete="CASCADE"),
        primary_key=True,
    )
    material_id: Mapped[int] = mapped_column(
        ForeignKey("materials.id", ondelete="CASCADE"),
        primary_key=True,
    )
    qty_per_piece: Mapped[float] = mapped_column(Float, nullable=False)

    mask = relationship("MetalizationMask", back_populates="material_out_rows")
    material = relationship("Material")
