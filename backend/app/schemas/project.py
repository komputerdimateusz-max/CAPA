from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field


class ProjectRead(BaseModel):
    id: int
    name: str = Field(..., examples=["Line A Revamp"])
    due_date: date | None = Field(None, examples=["2024-02-15"])
    status: str | None = Field(None, examples=["OPEN"])

    model_config = {"from_attributes": True}
