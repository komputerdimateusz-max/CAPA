from __future__ import annotations

from pydantic import BaseModel, Field, field_validator


class LabourCostUpdate(BaseModel):
    worker_type: str = Field(..., min_length=1)
    cost_pln: float = Field(..., ge=0)

    @field_validator("worker_type")
    @classmethod
    def validate_worker_type(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Worker type is required.")
        return cleaned
