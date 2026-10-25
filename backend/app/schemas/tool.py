from __future__ import annotations

from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.tools.enums import (
    ToolExecutionStatus,
    ToolPermission,
    ToolRiskLevel,
)


class ToolInputModel(BaseModel):
    """
    Base model for every ORVYN tool input.

    Unknown fields are rejected rather than silently
    ignored. Tool arguments may eventually originate
    from an LLM and must always be treated as untrusted.
    """

    model_config = ConfigDict(extra="forbid")


class ToolDefinition(BaseModel):
    """Public machine-readable description of a tool."""

    name: str = Field(min_length=1, max_length=100)
    description: str = Field(min_length=1, max_length=1000)
    version: str = Field(
        default="1.0.0",
        min_length=1,
        max_length=50,
    )
    risk_level: ToolRiskLevel = ToolRiskLevel.LOW
    permissions: list[ToolPermission] = Field(default_factory=list)
    requires_approval: bool = False
    input_schema: dict[str, Any] = Field(default_factory=dict)


class ToolExecutionContext(BaseModel):
    """
    Trusted execution context created only by ORVYN.

    Identity, permissions and approval state must never
    come from LLM-generated tool arguments.
    """

    model_config = ConfigDict(extra="forbid")

    user_id: UUID
    conversation_id: UUID | None = None
    message_id: UUID | None = None
    execution_id: UUID
    granted_permissions: list[ToolPermission] = Field(
        default_factory=list,
    )
    approved: bool = False


class ToolCallRequest(BaseModel):
    """Requested tool invocation."""

    model_config = ConfigDict(extra="forbid")

    tool_name: str = Field(min_length=1, max_length=100)
    arguments: dict[str, Any] = Field(default_factory=dict)


class ToolError(BaseModel):
    """
    Safe error representation.

    Internal exceptions, stack traces and secrets
    must not be exposed through this object.
    """

    code: str = Field(min_length=1, max_length=100)
    message: str = Field(min_length=1, max_length=1000)
    retryable: bool = False


class ToolExecutionResult(BaseModel):
    """Standard result returned by ORVYN's execution layer."""

    execution_id: UUID
    tool_name: str
    status: ToolExecutionStatus
    output: Any | None = None
    error: ToolError | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)