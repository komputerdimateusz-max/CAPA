from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from sqlalchemy.orm import Session

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
