from uuid import uuid4

import pytest

from app.schemas.tool import (
    ToolExecutionContext,
    ToolInputModel,
)
from app.tools.base import BaseTool
from app.tools.enums import (
    ToolPermission,
    ToolRiskLevel,
)
from app.tools.exceptions import (
    ToolPolicyConfigurationError,
)
from app.tools.policy import (
    evaluate_tool_authorization,
    minimum_required_risk,
    requires_approval,
    validate_tool_security_policy,
)
from app.tools.registry import (
    ToolRegistry,
)


class EmptyInput(ToolInputModel):
    pass


class PublicReadTool(
    BaseTool[EmptyInput]
):
    name = "public_read"

    description = (
        "Low-risk test tool requiring "
        "no privileged permission."
    )

    risk_level = ToolRiskLevel.LOW

    permissions = (
        ToolPermission.NONE,
    )

    requires_approval = False

    input_model = EmptyInput

    async def execute(
        self,
        *,
        arguments: EmptyInput,
        context: ToolExecutionContext,
    ):
        return {
            "ok": True,
        }


class FileWriteTool(
    BaseTool[EmptyInput]
):
    name = "file_write_test"

    description = (
        "Medium-risk test tool that "
        "writes a file."
    )

    risk_level = ToolRiskLevel.MEDIUM

    permissions = (
        ToolPermission.FILE_WRITE,
    )

    requires_approval = False

    input_model = EmptyInput

    async def execute(
        self,
        *,
        arguments: EmptyInput,
        context: ToolExecutionContext,
    ):
        return {
            "ok": True,
        }


class EmailSendTool(
    BaseTool[EmptyInput]
):
    name = "email_send_test"

    description = (
        "High-risk test tool for "
        "sending an email."
    )

    risk_level = ToolRiskLevel.HIGH

    permissions = (
        ToolPermission.EMAIL_SEND,
    )

    requires_approval = False

    input_model = EmptyInput

    async def execute(
        self,
        *,
        arguments: EmptyInput,
        context: ToolExecutionContext,
    ):
        return {
            "ok": True,
        }


class ExplicitApprovalTool(
    BaseTool[EmptyInput]
):
    name = "explicit_approval"

    description = (
        "Low-risk test tool that explicitly "
        "requests approval."
    )

    risk_level = ToolRiskLevel.LOW

    permissions = (
        ToolPermission.NONE,
    )

    requires_approval = True

    input_model = EmptyInput

    async def execute(
        self,
        *,
        arguments: EmptyInput,
        context: ToolExecutionContext,
    ):
        return {
            "ok": True,
        }


class UnsafeMisclassifiedTool(
    BaseTool[EmptyInput]
):
    name = "unsafe_email_tool"

    description = (
        "Intentionally unsafe test tool."
    )

    risk_level = ToolRiskLevel.LOW

    permissions = (
        ToolPermission.EMAIL_SEND,
    )

    requires_approval = False

    input_model = EmptyInput

    async def execute(
        self,
        *,
        arguments: EmptyInput,
        context: ToolExecutionContext,
    ):
        return {
            "ok": True,
        }


def build_context(
    *,
    permissions=None,
    approved=False,
):
    return ToolExecutionContext(
        user_id=uuid4(),
        execution_id=uuid4(),
        granted_permissions=(
            permissions
            or []
        ),
        approved=approved,
    )


def test_low_risk_none_permission_allowed():
    decision = (
        evaluate_tool_authorization(
            tool=PublicReadTool(),
            context=build_context(),
        )
    )

    assert (
        decision.allowed
        is True
    )

    assert (
        decision.approval_required
        is False
    )

    assert (
        decision.missing_permissions
        == []
    )


def test_missing_permission_denied():
    decision = (
        evaluate_tool_authorization(
            tool=FileWriteTool(),
            context=build_context(),
        )
    )

    assert (
        decision.allowed
        is False
    )

    assert (
        decision.approval_required
        is False
    )

    assert (
        decision.missing_permissions
        == [
            ToolPermission.FILE_WRITE,
        ]
    )


def test_medium_tool_allowed_with_permission():
    decision = (
        evaluate_tool_authorization(
            tool=FileWriteTool(),
            context=build_context(
                permissions=[
                    ToolPermission.FILE_WRITE,
                ],
            ),
        )
    )

    assert (
        decision.allowed
        is True
    )

    assert (
        decision.approval_required
        is False
    )


def test_high_risk_requires_approval():
    decision = (
        evaluate_tool_authorization(
            tool=EmailSendTool(),
            context=build_context(
                permissions=[
                    ToolPermission.EMAIL_SEND,
                ],
                approved=False,
            ),
        )
    )

    assert (
        decision.allowed
        is False
    )

    assert (
        decision.approval_required
        is True
    )


def test_high_risk_allowed_after_approval():
    decision = (
        evaluate_tool_authorization(
            tool=EmailSendTool(),
            context=build_context(
                permissions=[
                    ToolPermission.EMAIL_SEND,
                ],
                approved=True,
            ),
        )
    )

    assert (
        decision.allowed
        is True
    )

    assert (
        decision.approval_required
        is True
    )


def test_explicit_approval_flag_enforced():
    decision = (
        evaluate_tool_authorization(
            tool=ExplicitApprovalTool(),
            context=build_context(
                approved=False,
            ),
        )
    )

    assert (
        decision.allowed
        is False
    )

    assert (
        decision.approval_required
        is True
    )


def test_explicit_approval_succeeds():
    decision = (
        evaluate_tool_authorization(
            tool=ExplicitApprovalTool(),
            context=build_context(
                approved=True,
            ),
        )
    )

    assert (
        decision.allowed
        is True
    )


def test_email_send_minimum_risk_is_high():
    assert (
        minimum_required_risk(
            EmailSendTool()
        )
        == ToolRiskLevel.HIGH
    )


def test_file_write_minimum_risk_is_medium():
    assert (
        minimum_required_risk(
            FileWriteTool()
        )
        == ToolRiskLevel.MEDIUM
    )


def test_none_permission_minimum_risk_is_low():
    assert (
        minimum_required_risk(
            PublicReadTool()
        )
        == ToolRiskLevel.LOW
    )


def test_high_risk_automatically_requires_approval():
    assert (
        requires_approval(
            EmailSendTool()
        )
        is True
    )


def test_low_risk_does_not_require_approval_by_default():
    assert (
        requires_approval(
            PublicReadTool()
        )
        is False
    )


def test_misclassified_tool_policy_rejected():
    with pytest.raises(
        ToolPolicyConfigurationError
    ):
        validate_tool_security_policy(
            UnsafeMisclassifiedTool()
        )


def test_registry_rejects_misclassified_tool():
    registry = ToolRegistry()

    with pytest.raises(
        ToolPolicyConfigurationError
    ):
        registry.register(
            UnsafeMisclassifiedTool()
        )


def test_approval_does_not_bypass_missing_permission():
    decision = (
        evaluate_tool_authorization(
            tool=EmailSendTool(),
            context=build_context(
                permissions=[],
                approved=True,
            ),
        )
    )

    assert (
        decision.allowed
        is False
    )

    assert (
        decision.approval_required
        is False
    )

    assert (
        decision.missing_permissions
        == [
            ToolPermission.EMAIL_SEND,
        ]
    )


def test_unrelated_permission_does_not_grant_access():
    decision = (
        evaluate_tool_authorization(
            tool=FileWriteTool(),
            context=build_context(
                permissions=[
                    ToolPermission.FILE_READ,
                ],
            ),
        )
    )

    assert (
        decision.allowed
        is False
    )

    assert (
        ToolPermission.FILE_WRITE
        in decision.missing_permissions
    )