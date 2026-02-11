from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.repositories import analyses as analyses_repo
from app.repositories import tags as tags_repo
from app.schemas.analysis import AnalysisCreate, AnalysisListResponse, AnalysisRead
from app.schemas.tag import TagRead
from app.services import analyses as analyses_service

router = APIRouter(prefix="/api/analyses", tags=["analyses"])


def _serialize(analysis) -> AnalysisRead:
    return AnalysisRead(
        id=analysis.id,
        type=analysis.type,
        title=analysis.title,
        description=analysis.description or "",
        champion=analysis.champion,
        status=analysis.status,
        created_at=analysis.created_at,
        closed_at=analysis.closed_at,
        tags=[TagRead.model_validate(tag) for tag in analysis.tags],
    )


@router.get("", response_model=AnalysisListResponse)
def list_analyses(
    db: Session = Depends(get_db),
    tags: list[str] | None = Query(default=None),
    limit: int = Query(default=200, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
):
    rows, total = analyses_repo.list_analyses(db, tags=tags, limit=limit, offset=offset)
    return AnalysisListResponse(total=total, items=[_serialize(row) for row in rows])


@router.post("", response_model=AnalysisRead, status_code=status.HTTP_201_CREATED)
def create_analysis(payload: AnalysisCreate, db: Session = Depends(get_db)) -> AnalysisRead:
    analysis = analyses_service.create_analysis(
        db,
        analysis_type=payload.type,
        title=payload.title,
        description=payload.description,
        champion=payload.champion,
    )
    return _serialize(analysis)


@router.get("/{analysis_id}", response_model=AnalysisRead)
def get_analysis(analysis_id: str, db: Session = Depends(get_db)) -> AnalysisRead:
    analysis = analyses_repo.get_analysis(db, analysis_id)
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis not found")
    return _serialize(analysis)


@router.post("/{analysis_id}/tags/{tag_id}", response_model=AnalysisRead)
def add_analysis_tag(analysis_id: str, tag_id: int, db: Session = Depends(get_db)) -> AnalysisRead:
    analysis = analyses_repo.get_analysis(db, analysis_id)
    tag = tags_repo.get_tag(db, tag_id)
    if not analysis or not tag:
        raise HTTPException(status_code=404, detail="Analysis or tag not found")
    if tag not in analysis.tags:
        analysis.tags.append(tag)
    analysis = analyses_repo.update_analysis(db, analysis)
    return _serialize(analysis)


@router.delete("/{analysis_id}/tags/{tag_id}", response_model=AnalysisRead)
def remove_analysis_tag(analysis_id: str, tag_id: int, db: Session = Depends(get_db)) -> AnalysisRead:
    analysis = analyses_repo.get_analysis(db, analysis_id)
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis not found")
    analysis.tags = [tag for tag in analysis.tags if tag.id != tag_id]
    analysis = analyses_repo.update_analysis(db, analysis)
    return _serialize(analysis)
