from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field


class ProjectRead(BaseModel):
    id: int
    name: str = Field(..., examples=["Line A Revamp"])
    due_date: date | None = Field(None, examples=["2024-02-15"])
    status: str | None = Field(None, examples=["Serial production"])
    max_volume: int | None = Field(None, examples=[120000])
    flex_percent: float | None = Field(None, examples=[15.0])
    process_engineer_id: int | None = Field(None, examples=[2])

    model_config = {"from_attributes": True}
