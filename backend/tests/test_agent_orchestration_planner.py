
"""Regression tests for ORVYN's safe agent planner."""

from uuid import uuid4

import pytest

from app.agent_orchestration.planner import (
    AgentStep,
    PlanningError,
    StepKind,
    create_agent_plan,
    validate_agent_plan,
)


def make_plan(request: str):
    return create_agent_plan(
        user_id=uuid4(),
        conversation_id=uuid4(),
        request=request,
    )


def test_normal_request_creates_safe_plan():
    plan = make_plan(
        "Explain Python decorators."
    )

    validate_agent_plan(plan)

    assert plan.status.value == "planned"

    assert all(
        not step.requires_approval
        for step in plan.steps
    )


def test_file_request_requires_approval():
    plan = make_plan(
        "Create a Python study file."
    )

    validate_agent_plan(plan)

    approval_steps = [
        step
        for step in plan.steps
        if step.kind
        == StepKind.REQUEST_FILE_APPROVAL
    ]

    assert len(approval_steps) == 1
    assert approval_steps[0].requires_approval


def test_hinglish_file_request_requires_approval():
    plan = make_plan(
        "Mere liye Python notes file banao."
    )

    validate_agent_plan(plan)

    assert any(
        step.requires_approval
        for step in plan.steps
    )


def test_empty_request_is_rejected():
    with pytest.raises(PlanningError):
        make_plan("   ")


def test_long_request_is_rejected():
    with pytest.raises(PlanningError):
        make_plan("x" * 8193)


def test_plan_preserves_user_identity():
    user_id = uuid4()
    conversation_id = uuid4()

    plan = create_agent_plan(
        user_id=user_id,
        conversation_id=conversation_id,
        request="Explain SQL joins.",
    )

    assert plan.user_id == user_id
    assert plan.conversation_id == conversation_id


def test_unknown_dependency_is_rejected():
    plan = make_plan("Explain Python.")

    plan.steps[0].depends_on = [
        uuid4()
    ]

    with pytest.raises(PlanningError):
        validate_agent_plan(plan)


def test_circular_dependency_is_rejected():
    plan = make_plan("Explain Python.")

    first = plan.steps[0]
    second = plan.steps[1]

    first.depends_on = [second.id]
    second.depends_on = [first.id]

    with pytest.raises(PlanningError):
        validate_agent_plan(plan)


def test_unapproved_file_step_is_rejected():
    plan = make_plan(
        "Create a Python notes file."
    )

    file_step = next(
        step
        for step in plan.steps
        if step.kind
        == StepKind.REQUEST_FILE_APPROVAL
    )

    file_step.requires_approval = False

    with pytest.raises(PlanningError):
        validate_agent_plan(plan)


def test_duplicate_step_ids_are_rejected():
    plan = make_plan("Explain SQL.")

    plan.steps[1].id = plan.steps[0].id

    with pytest.raises(PlanningError):
        validate_agent_plan(plan)


def test_duplicate_dependencies_are_rejected():
    plan = make_plan("Explain Python.")

    first_id = plan.steps[0].id

    plan.steps[1].depends_on = [
        first_id,
        first_id,
    ]

    with pytest.raises(PlanningError):
        validate_agent_plan(plan)


def test_non_file_step_cannot_claim_approval():
    plan = make_plan("Explain SQL.")

    plan.steps[0].requires_approval = True

    with pytest.raises(PlanningError):
        validate_agent_plan(plan)
