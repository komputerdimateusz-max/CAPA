from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field, field_validator


class ProjectAssignmentToolRead(BaseModel):
    id: int
    tool_pn: str
    description: str | None = None


class ProjectAssignmentLineRead(BaseModel):
    id: int
    line_number: str


class ProjectCreate(BaseModel):
    name: str
    due_date: date | None = None
    status: str | None = None
    max_volume: int | None = None
    flex_percent: float | None = None
    process_engineer_id: int | None = None
    moulding_tool_ids: list[int] = Field(default_factory=list)
    assembly_line_ids: list[int] = Field(default_factory=list)

    @field_validator("moulding_tool_ids", "assembly_line_ids")
    @classmethod
    def remove_duplicates(cls, value: list[int]) -> list[int]:
        return list(dict.fromkeys(value))


class ProjectUpdate(ProjectCreate):
    pass


class ProjectRead(BaseModel):
    id: int
    name: str = Field(..., examples=["Line A Revamp"])
    due_date: date | None = Field(None, examples=["2024-02-15"])
    status: str | None = Field(None, examples=["Serial production"])
    max_volume: int | None = Field(None, examples=[120000])
    flex_percent: float | None = Field(None, examples=[15.0])
    process_engineer_id: int | None = Field(None, examples=[2])
    moulding_tools: list[ProjectAssignmentToolRead] = Field(default_factory=list)
    assembly_lines: list[ProjectAssignmentLineRead] = Field(default_factory=list)

    model_config = {"from_attributes": True}
