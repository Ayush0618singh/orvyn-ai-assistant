
"""Secure approval-to-agent-step binding rules.

This module does not grant approvals or execute tools.
It validates identity and relationship consistency.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from uuid import UUID


class ApprovalBindingError(ValueError):
    """Approval cannot be bound to this agent step."""


class ApprovalExecutionState(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"
    CONSUMED = "consumed"


@dataclass(frozen=True)
class PlanIdentity:
    plan_id: UUID
    user_id: UUID
    conversation_id: UUID
    status: str


@dataclass(frozen=True)
class StepIdentity:
    step_id: UUID
    plan_id: UUID
    kind: str
    requires_approval: bool
    status: str


@dataclass(frozen=True)
class ApprovalIdentity:
    approval_id: UUID
    user_id: UUID
    conversation_id: UUID
    tool_name: str
    status: str


@dataclass(frozen=True)
class ApprovalBinding:
    plan_id: UUID
    step_id: UUID
    approval_id: UUID
    user_id: UUID
    conversation_id: UUID


def validate_approval_binding(
    *,
    plan: PlanIdentity,
    step: StepIdentity,
    approval: ApprovalIdentity,
    expected_tool_name: str,
) -> ApprovalBinding:
    """Validate ownership and intended tool relationship.

    All identity objects must be constructed from
    trusted server-side database records, not directly
    from untrusted request JSON.
    """

    if plan.status in {
        "completed",
        "failed",
        "cancelled",
    }:
        raise ApprovalBindingError(
            "Cannot bind approval to terminal plan."
        )

    if step.plan_id != plan.plan_id:
        raise ApprovalBindingError(
            "Step does not belong to plan."
        )

    if approval.user_id != plan.user_id:
        raise ApprovalBindingError(
            "Approval belongs to another user."
        )

    if (
        approval.conversation_id
        != plan.conversation_id
    ):
        raise ApprovalBindingError(
            "Approval belongs to another conversation."
        )

    if not step.requires_approval:
        raise ApprovalBindingError(
            "Step does not require approval."
        )

    if step.kind != "request_file_approval":
        raise ApprovalBindingError(
            "Unsupported approval step kind."
        )

    if step.status not in {
        "pending",
        "awaiting_approval",
    }:
        raise ApprovalBindingError(
            "Step is not awaiting approval binding."
        )

    if not expected_tool_name.strip():
        raise ApprovalBindingError(
            "Expected tool name is missing."
        )

    if approval.tool_name != expected_tool_name:
        raise ApprovalBindingError(
            "Approval tool does not match expected tool."
        )

    if approval.status != (
        ApprovalExecutionState.PENDING.value
    ):
        raise ApprovalBindingError(
            "Only pending approvals can be bound."
        )

    return ApprovalBinding(
        plan_id=plan.plan_id,
        step_id=step.step_id,
        approval_id=approval.approval_id,
        user_id=plan.user_id,
        conversation_id=plan.conversation_id,
    )


def validate_execution_evidence(
    *,
    binding: ApprovalBinding,
    approval: ApprovalIdentity,
    execution_succeeded: bool,
) -> None:
    """Validate a trusted execution outcome.

    execution_succeeded must come from a verified
    server-side tool execution record, never from
    a client-supplied boolean.

    A consumed approval alone is insufficient.
    """

    if approval.approval_id != binding.approval_id:
        raise ApprovalBindingError(
            "Execution approval ID mismatch."
        )

    if approval.user_id != binding.user_id:
        raise ApprovalBindingError(
            "Execution user mismatch."
        )

    if (
        approval.conversation_id
        != binding.conversation_id
    ):
        raise ApprovalBindingError(
            "Execution conversation mismatch."
        )

    if approval.status != (
        ApprovalExecutionState.CONSUMED.value
    ):
        raise ApprovalBindingError(
            "Approval has not been consumed."
        )

    if not execution_succeeded:
        raise ApprovalBindingError(
            "Successful tool execution evidence is required."
        )
