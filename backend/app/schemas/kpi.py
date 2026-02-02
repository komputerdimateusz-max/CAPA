from __future__ import annotations

from pydantic import BaseModel, Field


class ActionsKPI(BaseModel):
    open_count: int = Field(..., examples=[5])
    overdue_count: int = Field(..., examples=[2])
    on_time_close_rate: float = Field(..., examples=[80.0])
    avg_time_to_close_days: float = Field(..., examples=[7.5])
    sum_days_late: int = Field(..., examples=[12])
