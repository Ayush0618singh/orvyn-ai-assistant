
"""Security tests for agent approval binding."""

from dataclasses import replace
from uuid import uuid4

import pytest

from app.agent_orchestration.approval_binding import (
    ApprovalBindingError,
    ApprovalIdentity,
    PlanIdentity,
    StepIdentity,
    validate_approval_binding,
    validate_execution_evidence,
)


TOOL_NAME = "workspace_file_write"


def sample_data():
    user_id = uuid4()
    conversation_id = uuid4()
    plan_id = uuid4()
    step_id = uuid4()
    approval_id = uuid4()

    plan = PlanIdentity(
        plan_id=plan_id,
        user_id=user_id,
        conversation_id=conversation_id,
        status="awaiting_approval",
    )

    step = StepIdentity(
        step_id=step_id,
        plan_id=plan_id,
        kind="request_file_approval",
        requires_approval=True,
        status="awaiting_approval",
    )

    approval = ApprovalIdentity(
        approval_id=approval_id,
        user_id=user_id,
        conversation_id=conversation_id,
        tool_name=TOOL_NAME,
        status="pending",
    )

    return plan, step, approval


def bind(plan, step, approval):
    return validate_approval_binding(
        plan=plan,
        step=step,
        approval=approval,
        expected_tool_name=TOOL_NAME,
    )


def test_valid_binding():
    plan, step, approval = sample_data()

    result = bind(plan, step, approval)

    assert result.plan_id == plan.plan_id
    assert result.step_id == step.step_id
    assert result.approval_id == (
        approval.approval_id
    )


def test_cross_user_approval_rejected():
    plan, step, approval = sample_data()

    approval = replace(
        approval,
        user_id=uuid4(),
    )

    with pytest.raises(
        ApprovalBindingError,
        match="another user",
    ):
        bind(plan, step, approval)


def test_cross_conversation_approval_rejected():
    plan, step, approval = sample_data()

    approval = replace(
        approval,
        conversation_id=uuid4(),
    )

    with pytest.raises(
        ApprovalBindingError,
        match="another conversation",
    ):
        bind(plan, step, approval)


def test_step_from_other_plan_rejected():
    plan, step, approval = sample_data()

    step = replace(
        step,
        plan_id=uuid4(),
    )

    with pytest.raises(
        ApprovalBindingError,
        match="does not belong",
    ):
        bind(plan, step, approval)


def test_non_approval_step_rejected():
    plan, step, approval = sample_data()

    step = replace(
        step,
        requires_approval=False,
    )

    with pytest.raises(
        ApprovalBindingError,
        match="does not require",
    ):
        bind(plan, step, approval)


def test_unsupported_step_kind_rejected():
    plan, step, approval = sample_data()

    step = replace(
        step,
        kind="summarize",
    )

    with pytest.raises(
        ApprovalBindingError,
        match="Unsupported",
    ):
        bind(plan, step, approval)


def test_wrong_tool_rejected():
    plan, step, approval = sample_data()

    approval = replace(
        approval,
        tool_name="unknown_tool",
    )

    with pytest.raises(
        ApprovalBindingError,
        match="tool does not match",
    ):
        bind(plan, step, approval)


def test_consumed_approval_cannot_be_bound():
    plan, step, approval = sample_data()

    approval = replace(
        approval,
        status="consumed",
    )

    with pytest.raises(
        ApprovalBindingError,
        match="Only pending",
    ):
        bind(plan, step, approval)


def test_rejected_approval_cannot_be_bound():
    plan, step, approval = sample_data()

    approval = replace(
        approval,
        status="rejected",
    )

    with pytest.raises(
        ApprovalBindingError,
        match="Only pending",
    ):
        bind(plan, step, approval)


def test_terminal_plan_rejected():
    plan, step, approval = sample_data()

    plan = replace(
        plan,
        status="cancelled",
    )

    with pytest.raises(
        ApprovalBindingError,
        match="terminal plan",
    ):
        bind(plan, step, approval)


def test_completed_step_rejected():
    plan, step, approval = sample_data()

    step = replace(
        step,
        status="completed",
    )

    with pytest.raises(
        ApprovalBindingError,
        match="not awaiting",
    ):
        bind(plan, step, approval)


def test_consumed_without_execution_success_rejected():
    plan, step, approval = sample_data()

    binding = bind(plan, step, approval)

    consumed = replace(
        approval,
        status="consumed",
    )

    with pytest.raises(
        ApprovalBindingError,
        match="Successful tool execution",
    ):
        validate_execution_evidence(
            binding=binding,
            approval=consumed,
            execution_succeeded=False,
        )


def test_verified_execution_evidence_accepted():
    plan, step, approval = sample_data()

    binding = bind(plan, step, approval)

    consumed = replace(
        approval,
        status="consumed",
    )

    validate_execution_evidence(
        binding=binding,
        approval=consumed,
        execution_succeeded=True,
    )


def test_execution_from_other_user_rejected():
    plan, step, approval = sample_data()

    binding = bind(plan, step, approval)

    consumed = replace(
        approval,
        user_id=uuid4(),
        status="consumed",
    )

    with pytest.raises(
        ApprovalBindingError,
        match="user mismatch",
    ):
        validate_execution_evidence(
            binding=binding,
            approval=consumed,
            execution_succeeded=True,
        )


def test_execution_with_wrong_approval_rejected():
    plan, step, approval = sample_data()

    binding = bind(plan, step, approval)

    consumed = replace(
        approval,
        approval_id=uuid4(),
        status="consumed",
    )

    with pytest.raises(
        ApprovalBindingError,
        match="approval ID mismatch",
    ):
        validate_execution_evidence(
            binding=binding,
            approval=consumed,
            execution_succeeded=True,
        )
