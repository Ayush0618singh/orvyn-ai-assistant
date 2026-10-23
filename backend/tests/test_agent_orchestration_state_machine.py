
"""Security and lifecycle tests for agent workflows."""

from dataclasses import replace
from uuid import uuid4

import pytest

from app.agent_orchestration.state_machine import (
    StepEvent,
    StepSnapshot,
    StepStatus,
    WorkflowError,
    WorkflowStatus,
    dependencies_completed,
    derive_workflow_status,
    transition_step,
    validate_steps,
)


def sample_steps():
    prepare_id = uuid4()
    approval_id = uuid4()
    summary_id = uuid4()

    steps = (
        StepSnapshot(
            id=prepare_id,
            kind="prepare_content",
            status=StepStatus.PENDING,
        ),
        StepSnapshot(
            id=approval_id,
            kind="request_file_approval",
            status=StepStatus.PENDING,
            depends_on=(prepare_id,),
            requires_approval=True,
        ),
        StepSnapshot(
            id=summary_id,
            kind="summarize",
            status=StepStatus.PENDING,
            depends_on=(approval_id,),
        ),
    )

    return steps


def update_status(
    steps,
    step_id,
    status,
):
    return tuple(
        replace(
            step,
            status=status,
        )
        if step.id == step_id
        else step
        for step in steps
    )


def test_initial_workflow_is_planned():
    assert derive_workflow_status(
        sample_steps()
    ) == WorkflowStatus.PLANNED


def test_prepare_step_can_start():
    steps = sample_steps()

    result = transition_step(
        step_id=steps[0].id,
        event=StepEvent.START,
        steps=steps,
    )

    assert result.next_status == (
        StepStatus.RUNNING
    )

    assert result.workflow_status == (
        WorkflowStatus.RUNNING
    )


def test_dependency_blocks_approval_step():
    steps = sample_steps()

    with pytest.raises(
        WorkflowError,
        match="Dependencies",
    ):
        transition_step(
            step_id=steps[1].id,
            event=StepEvent.REQUEST_APPROVAL,
            steps=steps,
        )


def test_approval_step_cannot_start_directly():
    steps = sample_steps()

    steps = update_status(
        steps,
        steps[0].id,
        StepStatus.COMPLETED,
    )

    with pytest.raises(
        WorkflowError,
        match="cannot start directly",
    ):
        transition_step(
            step_id=steps[1].id,
            event=StepEvent.START,
            steps=steps,
        )


def test_approval_step_enters_waiting_state():
    steps = sample_steps()

    steps = update_status(
        steps,
        steps[0].id,
        StepStatus.COMPLETED,
    )

    result = transition_step(
        step_id=steps[1].id,
        event=StepEvent.REQUEST_APPROVAL,
        steps=steps,
    )

    assert result.next_status == (
        StepStatus.AWAITING_APPROVAL
    )


def test_unverified_approval_is_rejected():
    steps = sample_steps()

    steps = update_status(
        steps,
        steps[1].id,
        StepStatus.AWAITING_APPROVAL,
    )

    with pytest.raises(
        WorkflowError,
        match="verification",
    ):
        transition_step(
            step_id=steps[1].id,
            event=StepEvent.APPROVAL_GRANTED,
            steps=steps,
        )


def test_verified_approval_allows_running():
    steps = sample_steps()

    steps = update_status(
        steps,
        steps[1].id,
        StepStatus.AWAITING_APPROVAL,
    )

    result = transition_step(
        step_id=steps[1].id,
        event=StepEvent.APPROVAL_GRANTED,
        steps=steps,
        approval_verified=True,
    )

    assert result.next_status == (
        StepStatus.RUNNING
    )


def test_unverified_rejection_is_rejected():
    steps = sample_steps()

    steps = update_status(
        steps,
        steps[1].id,
        StepStatus.AWAITING_APPROVAL,
    )

    with pytest.raises(
        WorkflowError,
        match="verification",
    ):
        transition_step(
            step_id=steps[1].id,
            event=StepEvent.APPROVAL_REJECTED,
            steps=steps,
        )


def test_verified_rejection_cancels_step():
    steps = sample_steps()

    steps = update_status(
        steps,
        steps[1].id,
        StepStatus.AWAITING_APPROVAL,
    )

    result = transition_step(
        step_id=steps[1].id,
        event=StepEvent.APPROVAL_REJECTED,
        steps=steps,
        approval_verified=True,
    )

    assert result.next_status == (
        StepStatus.CANCELLED
    )


def test_unverified_completion_is_rejected():
    steps = sample_steps()

    steps = update_status(
        steps,
        steps[0].id,
        StepStatus.RUNNING,
    )

    with pytest.raises(
        WorkflowError,
        match="execution evidence",
    ):
        transition_step(
            step_id=steps[0].id,
            event=StepEvent.COMPLETE,
            steps=steps,
        )


def test_verified_completion_succeeds():
    steps = sample_steps()

    steps = update_status(
        steps,
        steps[0].id,
        StepStatus.RUNNING,
    )

    result = transition_step(
        step_id=steps[0].id,
        event=StepEvent.COMPLETE,
        steps=steps,
        execution_verified=True,
    )

    assert result.next_status == (
        StepStatus.COMPLETED
    )


def test_completed_step_cannot_restart():
    steps = sample_steps()

    steps = update_status(
        steps,
        steps[0].id,
        StepStatus.COMPLETED,
    )

    with pytest.raises(
        WorkflowError,
        match="Terminal",
    ):
        transition_step(
            step_id=steps[0].id,
            event=StepEvent.START,
            steps=steps,
        )


def test_unknown_step_is_rejected():
    with pytest.raises(
        WorkflowError,
        match="not found",
    ):
        transition_step(
            step_id=uuid4(),
            event=StepEvent.START,
            steps=sample_steps(),
        )


def test_unknown_dependency_is_rejected():
    step = StepSnapshot(
        id=uuid4(),
        kind="summarize",
        status=StepStatus.PENDING,
        depends_on=(uuid4(),),
    )

    with pytest.raises(
        WorkflowError,
        match="Unknown dependency",
    ):
        validate_steps((step,))


def test_cycle_is_rejected():
    first_id = uuid4()
    second_id = uuid4()

    steps = (
        StepSnapshot(
            id=first_id,
            kind="prepare_content",
            status=StepStatus.PENDING,
            depends_on=(second_id,),
        ),
        StepSnapshot(
            id=second_id,
            kind="summarize",
            status=StepStatus.PENDING,
            depends_on=(first_id,),
        ),
    )

    with pytest.raises(
        WorkflowError,
        match="Circular",
    ):
        validate_steps(steps)


def test_duplicate_step_is_rejected():
    step = sample_steps()[0]

    with pytest.raises(
        WorkflowError,
        match="Duplicate step ID",
    ):
        validate_steps((step, step))


def test_file_step_must_require_approval():
    step = StepSnapshot(
        id=uuid4(),
        kind="request_file_approval",
        status=StepStatus.PENDING,
        requires_approval=False,
    )

    with pytest.raises(
        WorkflowError,
        match="requires approval",
    ):
        validate_steps((step,))


def test_unexpected_approval_flag_is_rejected():
    step = StepSnapshot(
        id=uuid4(),
        kind="summarize",
        status=StepStatus.PENDING,
        requires_approval=True,
    )

    with pytest.raises(
        WorkflowError,
        match="Unsupported",
    ):
        validate_steps((step,))


def test_pending_summary_waits_for_approval():
    steps = sample_steps()

    assert not dependencies_completed(
        steps[2],
        steps,
    )


def test_all_completed_means_completed():
    steps = tuple(
        replace(
            step,
            status=StepStatus.COMPLETED,
        )
        for step in sample_steps()
    )

    assert derive_workflow_status(
        steps
    ) == WorkflowStatus.COMPLETED


def test_failed_step_marks_workflow_failed():
    steps = sample_steps()

    steps = update_status(
        steps,
        steps[0].id,
        StepStatus.FAILED,
    )

    assert derive_workflow_status(
        steps
    ) == WorkflowStatus.FAILED


def test_cancelled_step_marks_workflow_cancelled():
    steps = sample_steps()

    steps = update_status(
        steps,
        steps[0].id,
        StepStatus.CANCELLED,
    )

    assert derive_workflow_status(
        steps
    ) == WorkflowStatus.CANCELLED


def test_running_step_can_fail():
    steps = sample_steps()

    steps = update_status(
        steps,
        steps[0].id,
        StepStatus.RUNNING,
    )

    result = transition_step(
        step_id=steps[0].id,
        event=StepEvent.FAIL,
        steps=steps,
    )

    assert result.next_status == (
        StepStatus.FAILED
    )


def test_pending_step_can_be_cancelled():
    steps = sample_steps()

    result = transition_step(
        step_id=steps[0].id,
        event=StepEvent.CANCEL,
        steps=steps,
    )

    assert result.next_status == (
        StepStatus.CANCELLED
    )
