from __future__ import annotations

from pydantic import BaseModel, Field, field_validator, model_validator


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
    price_per_unit: float | None = Field(default=None, ge=0)
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

    @model_validator(mode="after")
    def validate_make_buy_price_rules(self) -> "MaterialBase":
        if self.make_buy and self.price_per_unit is not None:
            self.price_per_unit = None
        if not self.make_buy and self.price_per_unit is None:
            raise ValueError("Price per unit is required for BUY material.")
        return self


class MaterialCreate(MaterialBase):
    pass


class MaterialUpdate(MaterialBase):
    pass
