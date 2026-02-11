from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.repositories import tags as tags_repo
from app.schemas.tag import TagCreate, TagRead

router = APIRouter(prefix="/api/tags", tags=["tags"])


@router.get("", response_model=list[TagRead])
def list_tags(db: Session = Depends(get_db)) -> list[TagRead]:
    return [TagRead.model_validate(tag) for tag in tags_repo.list_tags(db)]


@router.post("", response_model=TagRead, status_code=status.HTTP_201_CREATED)
def create_tag(payload: TagCreate, db: Session = Depends(get_db)) -> TagRead:
    if not payload.name.strip():
        raise HTTPException(status_code=400, detail="Tag name is required")
    existing = tags_repo.get_tag_by_name(db, payload.name)
    if existing:
        return TagRead.model_validate(existing)
    return TagRead.model_validate(tags_repo.create_tag(db, payload.name, payload.color))
