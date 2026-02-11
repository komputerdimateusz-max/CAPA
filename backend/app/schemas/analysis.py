from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field

from app.schemas.tag import TagRead


class AnalysisCreate(BaseModel):
    type: str
    title: str
    description: str = ""
    champion: str = ""


class AnalysisRead(BaseModel):
    id: str
    type: str
    title: str
    description: str = ""
    champion: str | None = None
    status: str
    created_at: date
    closed_at: date | None = None
    tags: list[TagRead] = Field(default_factory=list)

    model_config = {"from_attributes": True}


class AnalysisListResponse(BaseModel):
    total: int
    items: list[AnalysisRead]
