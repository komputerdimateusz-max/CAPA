from __future__ import annotations

from pydantic import BaseModel, Field, field_validator


class MaterialBase(BaseModel):
    part_number: str = Field(..., min_length=1)
    description: str | None = None
    unit: str = Field(..., min_length=1)
    price_per_unit: float = Field(..., ge=0)

    @field_validator("part_number")
    @classmethod
    def validate_part_number(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Part number is required.")
        return cleaned

    @field_validator("unit")
    @classmethod
    def validate_unit(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Unit is required.")
        return cleaned


class MaterialCreate(MaterialBase):
    pass


class MaterialUpdate(MaterialBase):
    pass
