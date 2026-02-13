from __future__ import annotations

from pydantic import BaseModel, Field, field_validator


class MouldingToolBase(BaseModel):
    tool_pn: str = Field(..., min_length=1)
    description: str | None = None
    ct_seconds: float = Field(..., ge=0)

    @field_validator("tool_pn")
    @classmethod
    def validate_tool_pn(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Tool P/N is required.")
        return cleaned


class MouldingToolCreate(MouldingToolBase):
    pass


class MouldingToolUpdate(MouldingToolBase):
    pass


class MouldingMachineBase(BaseModel):
    machine_number: str = Field(..., min_length=1)
    tonnage: int | None = Field(None, ge=0)
    tool_ids: list[int] = Field(default_factory=list)

    @field_validator("machine_number")
    @classmethod
    def validate_machine_number(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Machine number is required.")
        return cleaned

    @field_validator("tool_ids")
    @classmethod
    def validate_tool_ids_no_duplicates(cls, value: list[int]) -> list[int]:
        if len(value) != len(set(value)):
            raise ValueError("Tools assigned cannot contain duplicates.")
        return value


class MouldingMachineCreate(MouldingMachineBase):
    pass


class MouldingMachineUpdate(MouldingMachineBase):
    pass
