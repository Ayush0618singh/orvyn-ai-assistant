"""Schemas for explicit tool approval workflows."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.tools.enums import ToolApprovalStatus, ToolRiskLevel


class ToolApprovalRequest(BaseModel):
    """Exact tool action awaiting user approval."""

    model_config = ConfigDict(extra="forbid")

    approval_id: UUID
    user_id: UUID
    tool_name: str = Field(min_length=1, max_length=100)
    arguments: dict[str, Any] = Field(default_factory=dict)
    arguments_digest: str = Field(
        min_length=64,
        max_length=64,
        pattern=r"^[a-fA-F0-9]{64}$",
    )
    risk_level: ToolRiskLevel
    status: ToolApprovalStatus
    created_at: datetime
    expires_at: datetime
    decided_at: datetime | None = None
    consumed_at: datetime | None = None


class ToolApprovalDecision(BaseModel):
    """Result returned after approving or denying a request."""

    model_config = ConfigDict(extra="forbid")

    approval_id: UUID
    status: ToolApprovalStatus
    decided_at: datetime


class ToolApprovalVerification(BaseModel):
    """Result of verifying a stored tool approval."""

    model_config = ConfigDict(extra="forbid")

    approval_id: UUID
    verified: bool
    consumed: bool