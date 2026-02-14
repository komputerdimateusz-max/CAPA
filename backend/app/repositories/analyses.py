from __future__ import annotations

from datetime import date
from typing import Iterable

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.models.analysis import (
    ALLOWED_OBSERVED_PROCESS_TYPES,
    Analysis,
    Analysis5Why,
    OBSERVED_PROCESS_TYPE_ASSEMBLY,
    OBSERVED_PROCESS_TYPE_METALIZATION,
    OBSERVED_PROCESS_TYPE_MOULDING,
)
from app.models.tag import Tag


ANALYSIS_TYPES = ["5WHY", "ISHIKAWA", "8D", "A3"]
ANALYSIS_STATUSES = ["Open", "Closed"]


def _analysis_load_options():
    return (
        selectinload(Analysis.tags),
        selectinload(Analysis.details_5why).selectinload(Analysis5Why.moulding_tools),
        selectinload(Analysis.details_5why).selectinload(Analysis5Why.metalization_masks),
        selectinload(Analysis.details_5why).selectinload(Analysis5Why.assembly_references),
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


def set_analysis_observed_components(
    db: Session,
    analysis_id: str,
    process_type: str | None,
    component_ids: list[int],
) -> Analysis5Why:
    details = get_analysis_5why(db, analysis_id)
    if details is None:
        raise ValueError("5WHY details not found")

    normalized_process_type = (process_type or "").strip().lower() or None
    if normalized_process_type and normalized_process_type not in ALLOWED_OBSERVED_PROCESS_TYPES:
        raise ValueError("Invalid process type")

    details.observed_process_type = normalized_process_type
    unique_ids = sorted(set(component_ids))

    details.moulding_tools = []
    details.metalization_masks = []
    details.assembly_references = []

    if normalized_process_type == OBSERVED_PROCESS_TYPE_MOULDING and unique_ids:
        from app.repositories import actions as actions_repo

        details.moulding_tools = [
            tool for component_id in unique_ids if (tool := actions_repo.get_moulding_tool_by_id(db, component_id)) is not None
        ]
    elif normalized_process_type == OBSERVED_PROCESS_TYPE_METALIZATION and unique_ids:
        from app.repositories import actions as actions_repo

        details.metalization_masks = [
            mask for component_id in unique_ids if (mask := actions_repo.get_metalization_mask_by_id(db, component_id)) is not None
        ]
    elif normalized_process_type == OBSERVED_PROCESS_TYPE_ASSEMBLY and unique_ids:
        from app.repositories import actions as actions_repo

        details.assembly_references = [
            reference
            for component_id in unique_ids
            if (reference := actions_repo.get_assembly_reference_by_id(db, component_id)) is not None
        ]

    return update_analysis_5why(db, details)
