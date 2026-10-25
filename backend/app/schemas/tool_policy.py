"""Schemas for tool authorization and risk decisions."""

from pydantic import BaseModel, ConfigDict, Field

from app.tools.enums import ToolPermission, ToolRiskLevel


class ToolAuthorizationDecision(BaseModel):
    """Result of ORVYN's tool permission and risk evaluation."""

    model_config = ConfigDict(extra="forbid")

    allowed: bool
    approval_required: bool
    risk_level: ToolRiskLevel

    required_permissions: list[ToolPermission] = Field(
        default_factory=list,
    )
    missing_permissions: list[ToolPermission] = Field(
        default_factory=list,
    )
    reason: str = Field(min_length=1, max_length=1000)