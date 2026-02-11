from __future__ import annotations

from pydantic import BaseModel, Field


class TagCreate(BaseModel):
    name: str = Field(..., examples=["safety"])
    color: str | None = Field(None, examples=["#2563eb"])


class TagRead(BaseModel):
    id: int
    name: str
    color: str | None = None

    model_config = {"from_attributes": True}
