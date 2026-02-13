from __future__ import annotations

from pydantic import BaseModel, Field, field_validator


class AssemblyLineBase(BaseModel):
    line_number: str = Field(..., min_length=1)
    ct_seconds: float = Field(..., ge=0)
    hc: int = Field(default=0, ge=0)
    hc_map: dict[str, float] = Field(default_factory=dict)

    @field_validator("line_number")
    @classmethod
    def validate_line_number(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Line number is required.")
        return cleaned


class AssemblyLineCreate(AssemblyLineBase):
    pass


class AssemblyLineUpdate(BaseModel):
    line_number: str | None = Field(default=None, min_length=1)
    ct_seconds: float | None = Field(default=None, ge=0)
    hc: int | None = Field(default=None, ge=0)
    hc_map: dict[str, float] | None = None

    @field_validator("line_number")
    @classmethod
    def validate_line_number(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Line number is required.")
        return cleaned
