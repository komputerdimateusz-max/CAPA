from __future__ import annotations

from pydantic import BaseModel, Field, field_validator


MATERIAL_CATEGORY_OPTIONS = (
    "Raw material",
    "Internal plastic parts",
    "metal parts",
    "sub-group",
    "FG",
)


class MaterialBase(BaseModel):
    part_number: str = Field(..., min_length=1)
    description: str | None = None
    unit: str = Field(..., min_length=1)
    price_per_unit: float = Field(..., ge=0)
    category: str = Field(..., min_length=1)
    make_buy: bool = False

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

    @field_validator("category")
    @classmethod
    def validate_category(cls, value: str) -> str:
        cleaned = value.strip()
        if cleaned not in MATERIAL_CATEGORY_OPTIONS:
            raise ValueError(f"Category must be one of: {', '.join(MATERIAL_CATEGORY_OPTIONS)}")
        return cleaned


class MaterialCreate(MaterialBase):
    pass


class MaterialUpdate(MaterialBase):
    pass
