
"""Response schemas for ORVYN agent execution monitoring."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class AgentExecutionMetricsResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    total: int = Field(ge=0)
    started: int = Field(ge=0)
    succeeded: int = Field(ge=0)
    failed: int = Field(ge=0)
    cancelled: int = Field(ge=0)
    stale_started: int = Field(ge=0)

    stale_after_minutes: int = Field(ge=15, le=1440)
