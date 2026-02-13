from __future__ import annotations

from pydantic import BaseModel, Field, field_validator


class MetalizationMaskBase(BaseModel):
    mask_pn: str = Field(..., min_length=1)
    description: str | None = None
    ct_seconds: float = Field(..., ge=0)

    @field_validator("mask_pn")
    @classmethod
    def validate_mask_pn(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Mask P/N is required.")
        return cleaned


class MetalizationMaskCreate(MetalizationMaskBase):
    pass


class MetalizationMaskUpdate(MetalizationMaskBase):
    pass


class MetalizationChamberBase(BaseModel):
    chamber_number: str = Field(..., min_length=1)
    mask_ids: list[int] = Field(default_factory=list)

    @field_validator("chamber_number")
    @classmethod
    def validate_chamber_number(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Chamber number is required.")
        return cleaned

    @field_validator("mask_ids")
    @classmethod
    def validate_mask_ids_no_duplicates(cls, value: list[int]) -> list[int]:
        if len(value) != len(set(value)):
            raise ValueError("Masks assigned cannot contain duplicates.")
        return value


class MetalizationChamberCreate(MetalizationChamberBase):
    pass


class MetalizationChamberUpdate(MetalizationChamberBase):
    pass
