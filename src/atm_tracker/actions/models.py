from __future__ import annotations

from datetime import date
from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator


Status = Literal["OPEN", "IN_PROGRESS", "CLOSED"]


class ActionCreate(BaseModel):
    title: str = Field(min_length=3, max_length=200)
    description: str = Field(default="", max_length=2000)
    line: str = Field(min_length=1, max_length=50)
    project_or_family: str = Field(default="", max_length=80)
    owner: str = Field(default="", max_length=80)
    champion: str = Field(default="", max_length=80)

    status: Status = "OPEN"
    created_at: date
    implemented_at: Optional[date] = None
    closed_at: Optional[date] = None

    cost_internal_hours: float = Field(default=0.0, ge=0.0)
    cost_external_eur: float = Field(default=0.0, ge=0.0)
    cost_material_eur: float = Field(default=0.0, ge=0.0)

    tags: str = Field(default="", max_length=300)  # comma-separated for MVP

    @field_validator("closed_at")
    @classmethod
    def closed_requires_status(cls, v, info):
        status = info.data.get("status")
        if status == "CLOSED" and v is None:
            raise ValueError("closed_at is required when status=CLOSED")
        return v

    @field_validator("implemented_at")
    @classmethod
    def implemented_before_closed(cls, v, info):
        closed_at = info.data.get("closed_at")
        if v and closed_at and v > closed_at:
            raise ValueError("implemented_at cannot be after closed_at")
        return v
