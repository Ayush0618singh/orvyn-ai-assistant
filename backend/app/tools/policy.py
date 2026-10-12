from __future__ import annotations

from app.schemas.tool import (
    ToolExecutionContext,
)
from app.schemas.tool_policy import (
    ToolAuthorizationDecision,
)
from app.tools.base import BaseTool
from app.tools.enums import (
    ToolPermission,
    ToolRiskLevel,
)
from app.tools.exceptions import (
    ToolPolicyConfigurationError,
)


_RISK_ORDER = {
    ToolRiskLevel.LOW: 10,
    ToolRiskLevel.MEDIUM: 20,
    ToolRiskLevel.HIGH: 30,
    ToolRiskLevel.CRITICAL: 40,
}


_PERMISSION_MINIMUM_RISK = {
    ToolPermission.NONE:
        ToolRiskLevel.LOW,

    ToolPermission.WEB_READ:
        ToolRiskLevel.LOW,

    ToolPermission.FILE_READ:
        ToolRiskLevel.LOW,

    ToolPermission.FILE_WRITE:
        ToolRiskLevel.MEDIUM,

    ToolPermission.MEMORY_READ:
        ToolRiskLevel.LOW,

    ToolPermission.MEMORY_WRITE:
        ToolRiskLevel.MEDIUM,

    ToolPermission.NOTES_READ:
        ToolRiskLevel.LOW,

    ToolPermission.NOTES_WRITE:
        ToolRiskLevel.MEDIUM,

    ToolPermission.TASKS_READ:
        ToolRiskLevel.LOW,

    ToolPermission.TASKS_WRITE:
        ToolRiskLevel.MEDIUM,

    ToolPermission.CALENDAR_READ:
        ToolRiskLevel.LOW,

    ToolPermission.CALENDAR_WRITE:
        ToolRiskLevel.HIGH,

    ToolPermission.EMAIL_READ:
        ToolRiskLevel.MEDIUM,

    ToolPermission.EMAIL_SEND:
        ToolRiskLevel.HIGH,

    ToolPermission.CODE_EXECUTE:
        ToolRiskLevel.HIGH,

    ToolPermission.SYSTEM_READ:
        ToolRiskLevel.MEDIUM,

    ToolPermission.SYSTEM_WRITE:
        ToolRiskLevel.CRITICAL,
}


_APPROVAL_RISK_LEVELS = {
    ToolRiskLevel.HIGH,
    ToolRiskLevel.CRITICAL,
}


def normalize_required_permissions(
    tool: BaseTool,
) -> list[ToolPermission]:
    """
    Return unique effective permissions required by a tool.

    NONE means no capability permission is required and is
    therefore removed from the effective requirement list.
    """

    permissions: list[
        ToolPermission
    ] = []

    seen: set[
        ToolPermission
    ] = set()

    for permission in tool.permissions:
        if (
            permission
            == ToolPermission.NONE
        ):
            continue

        if permission in seen:
            continue

        seen.add(
            permission
        )

        permissions.append(
            permission
        )

    return permissions


def minimum_required_risk(
    tool: BaseTool,
) -> ToolRiskLevel:
    """
    Calculate the minimum safe risk level implied by the
    capabilities requested by the tool.
    """

    required_permissions = (
        normalize_required_permissions(
            tool
        )
    )

    if not required_permissions:
        return ToolRiskLevel.LOW

    minimum = ToolRiskLevel.LOW

    for permission in required_permissions:
        permission_risk = (
            _PERMISSION_MINIMUM_RISK[
                permission
            ]
        )

        if (
            _RISK_ORDER[
                permission_risk
            ]
            >
            _RISK_ORDER[
                minimum
            ]
        ):
            minimum = (
                permission_risk
            )

    return minimum


def validate_tool_security_policy(
    tool: BaseTool,
) -> None:
    """
    Ensure the tool cannot understate the risk associated
    with its requested permissions.
    """

    minimum = minimum_required_risk(
        tool
    )

    declared = tool.risk_level

    if (
        _RISK_ORDER[declared]
        <
        _RISK_ORDER[minimum]
    ):
        raise ToolPolicyConfigurationError(
            (
                f"Tool '{tool.name}' declares risk "
                f"'{declared.value}' but its permissions "
                f"require at least '{minimum.value}'."
            )
        )


def requires_approval(
    tool: BaseTool,
) -> bool:
    """
    Determine whether ORVYN must obtain explicit approval.

    Tool authors may opt into approval at any risk level,
    while HIGH and CRITICAL tools always require approval.
    """

    if tool.requires_approval:
        return True

    return (
        tool.risk_level
        in _APPROVAL_RISK_LEVELS
    )


def evaluate_tool_authorization(
    *,
    tool: BaseTool,
    context: ToolExecutionContext,
) -> ToolAuthorizationDecision:
    """
    Evaluate whether a trusted ORVYN execution context may
    execute the requested tool.

    Order:
    1. validate tool security metadata,
    2. check capability permissions,
    3. enforce approval policy,
    4. permit immediate execution only when all gates pass.
    """

    validate_tool_security_policy(
        tool
    )

    required_permissions = (
        normalize_required_permissions(
            tool
        )
    )

    granted_permissions = set(
        context.granted_permissions
    )

    missing_permissions = [
        permission
        for permission
        in required_permissions
        if permission
        not in granted_permissions
    ]

    if missing_permissions:
        return ToolAuthorizationDecision(
            allowed=False,
            approval_required=False,
            risk_level=tool.risk_level,
            required_permissions=(
                required_permissions
            ),
            missing_permissions=(
                missing_permissions
            ),
            reason=(
                "Execution denied because one or more "
                "required tool permissions are missing."
            ),
        )

    approval_required = (
        requires_approval(
            tool
        )
    )

    if (
        approval_required
        and not context.approved
    ):
        return ToolAuthorizationDecision(
            allowed=False,
            approval_required=True,
            risk_level=tool.risk_level,
            required_permissions=(
                required_permissions
            ),
            missing_permissions=[],
            reason=(
                "Execution requires explicit user approval."
            ),
        )

    return ToolAuthorizationDecision(
        allowed=True,
        approval_required=(
            approval_required
        ),
        risk_level=tool.risk_level,
        required_permissions=(
            required_permissions
        ),
        missing_permissions=[],
        reason=(
            "Tool execution is authorized."
        ),
    )