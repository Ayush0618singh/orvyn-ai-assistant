
"""Public response schemas for agent execution audits."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


AuditStatus = Literal[
    "started",
    "succeeded",
    "failed",
    "cancelled",
]


class AgentExecutionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    status: AuditStatus
    step_count: int
    completed_steps: int
    failure_category: str | None
    started_at: datetime
    last_heartbeat_at: datetime | None = None
    finished_at: datetime | None
    duration_ms: int | None


class AgentExecutionListResponse(BaseModel):
    items: list[AgentExecutionResponse]
    total: int = Field(ge=0)
    limit: int = Field(ge=1, le=100)
    offset: int = Field(ge=0)
