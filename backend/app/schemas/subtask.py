from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, Field


class SubtaskBase(BaseModel):
    title: str = Field(..., examples=["Validate new sensor"])
    status: str = Field("OPEN", examples=["OPEN"])
    due_date: date | None = Field(None, examples=["2024-01-18"])
    closed_at: datetime | None = Field(None, examples=["2024-01-17T15:00:00"])
    created_at: datetime | None = Field(None, examples=["2024-01-10T09:00:00"])


class SubtaskCreate(SubtaskBase):
    title: str


class SubtaskUpdate(BaseModel):
    title: str | None = None
    status: str | None = None
    due_date: date | None = None
    closed_at: datetime | None = None


class SubtaskRead(SubtaskBase):
    id: int
    action_id: int

    model_config = {"from_attributes": True}
