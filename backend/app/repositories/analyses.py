from __future__ import annotations

from datetime import date
from typing import Iterable

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.models.analysis import Analysis, Analysis5Why
from app.models.tag import Tag

ANALYSIS_TYPES = ["5WHY", "ISHIKAWA", "8D", "A3"]
ANALYSIS_STATUSES = ["Open", "Closed"]


def _analysis_load_options():
    return (
        selectinload(Analysis.tags),
        selectinload(Analysis.details_5why),
        selectinload(Analysis.actions),
    )


def list_analyses(
    db: Session,
    tags: list[str] | None = None,
    limit: int = 100,
    offset: int = 0,
) -> tuple[list[Analysis], int]:
    stmt = select(Analysis).options(*_analysis_load_options())
    if tags:
        for tag_name in tags:
            stmt = stmt.where(Analysis.tags.any(func.lower(Tag.name) == tag_name.lower()))
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    stmt = stmt.order_by(Analysis.created_at.desc(), Analysis.id.desc()).limit(limit).offset(offset)
    return list(db.scalars(stmt).all()), total


def list_analysis_ids(db: Session) -> list[str]:
    return list(db.scalars(select(Analysis.id)).all())


def get_analysis(db: Session, analysis_id: str) -> Analysis | None:
    stmt = select(Analysis).options(*_analysis_load_options()).where(Analysis.id == analysis_id)
    return db.scalar(stmt)


def get_analysis_5why(db: Session, analysis_id: str) -> Analysis5Why | None:
    return db.get(Analysis5Why, analysis_id)


def create_analysis(db: Session, payload: dict[str, object]) -> Analysis:
    analysis = Analysis(**payload)
    db.add(analysis)
    db.commit()
    db.refresh(analysis)
    return analysis


def create_analysis_5why(db: Session, payload: dict[str, object]) -> Analysis5Why:
    details = Analysis5Why(**payload)
    db.add(details)
    db.commit()
    db.refresh(details)
    return details


def update_analysis(db: Session, analysis: Analysis) -> Analysis:
    db.add(analysis)
    db.commit()
    db.refresh(analysis)
    return analysis


def update_analysis_5why(db: Session, details: Analysis5Why) -> Analysis5Why:
    db.add(details)
    db.commit()
    db.refresh(details)
    return details


def generate_analysis_id(analysis_type: str, existing_ids: Iterable[str] | None = None) -> str:
    if analysis_type not in ANALYSIS_TYPES:
        raise ValueError("Invalid analysis type.")
    current_year = date.today().year
    prefix = f"{analysis_type}-{current_year}-"
    max_seq = 0
    if existing_ids:
        for value in existing_ids:
            text = str(value)
            if text.startswith(prefix):
                maybe_seq = text.removeprefix(prefix)
                if len(maybe_seq) == 4 and maybe_seq.isdigit():
                    max_seq = max(max_seq, int(maybe_seq))
    return f"{prefix}{max_seq + 1:04d}"
