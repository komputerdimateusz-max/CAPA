from __future__ import annotations

from dataclasses import dataclass
from datetime import date

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


def list_analyses_page(page: int, page_size: int) -> tuple[list[dict[str, object]], int]:
    analyses = analyses_repo.list_analyses()
    analyses.sort(
        key=lambda row: (
            row.get("created_at") or date.min,
            str(row.get("analysis_id") or ""),
        ),
        reverse=True,
    )
    total = len(analyses)
    start = (page - 1) * page_size
    end = start + page_size
    return analyses[start:end], total


def create_analysis(
    analysis_type: str,
    title: str,
    description: str,
    champion: str,
) -> dict[str, object]:
    analysis_type = analysis_type.strip().upper()
    if analysis_type not in analyses_repo.ANALYSIS_TYPES:
        raise ValueError("Select a valid analysis template.")
    title_clean = " ".join(title.split()).strip()
    if not title_clean:
        raise ValueError("Title is required.")
    payload = {
        "analysis_id": analyses_repo.generate_analysis_id(analysis_type),
        "type": analysis_type,
        "title": title_clean,
        "description": description.strip(),
        "champion": champion.strip(),
        "status": "Open",
        "created_at": date.today().isoformat(),
        "closed_at": "",
    }
    analyses_repo.upsert_analysis(payload)
    return payload
