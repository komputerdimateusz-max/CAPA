from __future__ import annotations

from datetime import date, datetime
from pydantic import BaseModel, Field

from app.schemas.tag import TagRead


class ActionBase(BaseModel):
    title: str = Field(..., examples=["Reduce scrap on Line A"])
    description: str | None = Field("", examples=["Investigate root cause and implement fix."])
    project_id: int | None = Field(None, examples=[1])
    champion_id: int | None = Field(None, examples=[2])
    owner: str | None = Field(None, examples=["J. Doe"])
    status: str = Field("OPEN", examples=["OPEN"])
    created_at: datetime | None = Field(None, examples=["2024-01-10T08:00:00"])
    due_date: date | None = Field(None, examples=["2024-01-20"])
    closed_at: datetime | None = Field(None, examples=["2024-01-19T12:30:00"])
    tags: list[str] = Field(default_factory=list, examples=[["scrap", "line-a"]])
    priority: str | None = Field(None, examples=["HIGH"])


class ActionCreate(ActionBase):
    title: str


class ActionUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    project_id: int | None = None
    champion_id: int | None = None
    owner: str | None = None
    status: str | None = None
    due_date: date | None = None
    closed_at: datetime | None = None
    tags: list[str] | None = None
    priority: str | None = None


class ActionRead(BaseModel):
    id: int
    title: str
    description: str | None = ""
    project_id: int | None = None
    project_name: str | None = None
    champion_id: int | None = None
    champion_name: str | None = None
    owner: str | None = None
    status: str
    created_at: datetime | None = None
    due_date: date | None = None
    closed_at: datetime | None = None
    tags: list[TagRead] = Field(default_factory=list)
    priority: str | None = None
    days_late: int = 0
    time_to_close_days: int | None = None
    on_time_close: bool | None = None

    model_config = {"from_attributes": True}


class ActionListResponse(BaseModel):
    total: int
    items: list[ActionRead]


class ActionDetailResponse(ActionRead):
    pass
