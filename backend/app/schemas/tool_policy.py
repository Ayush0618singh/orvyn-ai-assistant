from pydantic import BaseModel, Field

from app.tools.enums import (
    ToolPermission,
    ToolRiskLevel,
)


class ToolAuthorizationDecision(BaseModel):
    """
    Result of ORVYN's tool permission and risk evaluation.

    allowed means the tool may execute immediately.

    approval_required means execution must stop and obtain
    explicit trusted approval before retrying.
    """

    allowed: bool

    approval_required: bool

    risk_level: ToolRiskLevel

    required_permissions: list[

        ToolPermission
    ] = Field(
        default_factory=list,
    )

    missing_permissions: list[
        ToolPermission
    ] = Field(
        default_factory=list,
    )

    reason: str