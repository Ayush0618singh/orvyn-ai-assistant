
"""Request and response schemas for durable tool approvals."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ToolApprovalResponse(BaseModel):
    """Owned approval request visible to its user."""

    model_config = ConfigDict(
        from_attributes=True,
        extra="forbid",
    )

    id: UUID
    tool_name: str
    arguments: dict[str, Any]
    risk_level: str
    status: str
    created_at: datetime
    expires_at: datetime
    decided_at: datetime | None = None
    consumed_at: datetime | None = None


class ToolApprovalListResponse(BaseModel):
    """Paginated list of owned approval requests."""

    items: list[ToolApprovalResponse] = Field(
        default_factory=list
    )
    total: int
    limit: int
    offset: int


class ToolApprovalDecisionResponse(BaseModel):
    """Result of an explicit approval decision."""

    id: UUID
    status: str
    decided_at: datetime
