from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from sqlalchemy.orm import Session

from app.models.analysis import (
    OBSERVED_PROCESS_TYPE_ASSEMBLY,
    OBSERVED_PROCESS_TYPE_METALIZATION,
    OBSERVED_PROCESS_TYPE_MOULDING,
)
from app.repositories import analyses as analyses_repo


@dataclass(frozen=True)
class AnalysisTemplate:
    code: str
    label: str
    description: str


ANALYSIS_TEMPLATES = (
    AnalysisTemplate(code="5WHY", label="5 Why", description="Root cause laddering with 5 whys."),
    AnalysisTemplate(code="ISHIKAWA", label="Ishikawa", description="Fishbone diagram of contributing causes."),
    AnalysisTemplate(code="8D", label="8D", description="Structured eight-discipline problem solving."),
    AnalysisTemplate(code="A3", label="A3", description="A3 storytelling for PDCA."),
)


def list_analysis_templates() -> tuple[AnalysisTemplate, ...]:
    return ANALYSIS_TEMPLATES


def list_analyses_page(
    db: Session,
    page: int,
    page_size: int,
    tags: list[str] | None = None,
):
    return analyses_repo.list_analyses(db, tags=tags, limit=page_size, offset=(page - 1) * page_size)


def create_analysis(
    db: Session,
    analysis_type: str,
    title: str,
    description: str,
    champion: str,
):
    analysis_type = analysis_type.strip().upper()
    if analysis_type not in analyses_repo.ANALYSIS_TYPES:
        raise ValueError("Select a valid analysis template.")
    title_clean = " ".join(title.split()).strip()
    if not title_clean:
        raise ValueError("Title is required.")

    payload = {
        "id": analyses_repo.generate_analysis_id(analysis_type, analyses_repo.list_analysis_ids(db)),
        "type": analysis_type,
        "title": title_clean,
        "description": description.strip(),
        "champion": champion.strip(),
        "status": "Open",
        "created_at": date.today(),
        "closed_at": None,
    }
    return analyses_repo.create_analysis(db, payload)


def set_observed_process(db: Session, analysis_id: str, process_type: str | None):
    return analyses_repo.set_analysis_observed_components(db, analysis_id, process_type, [])


def add_observed_component(db: Session, analysis_id: str, process_type: str, component_id: int):
    details = analyses_repo.get_analysis_5why(db, analysis_id)
    if details is None:
        raise ValueError("5WHY details not found")

    if process_type == OBSERVED_PROCESS_TYPE_MOULDING:
        current_ids = [item.id for item in details.moulding_tools]
    elif process_type == OBSERVED_PROCESS_TYPE_METALIZATION:
        current_ids = [item.id for item in details.metalization_masks]
    elif process_type == OBSERVED_PROCESS_TYPE_ASSEMBLY:
        current_ids = [item.id for item in details.assembly_references]
    else:
        raise ValueError("Invalid process type")

    if component_id not in current_ids:
        current_ids.append(component_id)
    return analyses_repo.set_analysis_observed_components(db, analysis_id, process_type, current_ids)


def remove_observed_component(db: Session, analysis_id: str, process_type: str, component_id: int):
    details = analyses_repo.get_analysis_5why(db, analysis_id)
    if details is None:
        raise ValueError("5WHY details not found")

    if process_type == OBSERVED_PROCESS_TYPE_MOULDING:
        current_ids = [item.id for item in details.moulding_tools]
    elif process_type == OBSERVED_PROCESS_TYPE_METALIZATION:
        current_ids = [item.id for item in details.metalization_masks]
    elif process_type == OBSERVED_PROCESS_TYPE_ASSEMBLY:
        current_ids = [item.id for item in details.assembly_references]
    else:
        raise ValueError("Invalid process type")

    kept_ids = [item_id for item_id in current_ids if item_id != component_id]
    return analyses_repo.set_analysis_observed_components(db, analysis_id, process_type, kept_ids)
