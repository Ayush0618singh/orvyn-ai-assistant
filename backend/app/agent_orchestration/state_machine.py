
"""ORVYN secure agent step lifecycle.

This module manages validated state transitions only.

It never:
- executes a tool
- approves an action
- writes a workspace file
- trusts a client-supplied execution result

Database authorization, approval verification and
transaction locking belong to the service layer.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Iterable
from uuid import UUID


class WorkflowError(ValueError):
    """An invalid workflow or transition."""


class StepStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    AWAITING_APPROVAL = "awaiting_approval"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class WorkflowStatus(str, Enum):
    PLANNED = "planned"
    RUNNING = "running"
    AWAITING_APPROVAL = "awaiting_approval"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class StepEvent(str, Enum):
    START = "start"
    REQUEST_APPROVAL = "request_approval"
    APPROVAL_GRANTED = "approval_granted"
    APPROVAL_REJECTED = "approval_rejected"
    COMPLETE = "complete"
    FAIL = "fail"
    CANCEL = "cancel"


@dataclass(frozen=True)
class StepSnapshot:
    id: UUID
    kind: str
    status: StepStatus
    depends_on: tuple[UUID, ...] = ()
    requires_approval: bool = False


@dataclass(frozen=True)
class TransitionResult:
    step_id: UUID
    previous_status: StepStatus
    next_status: StepStatus
    workflow_status: WorkflowStatus


def validate_steps(
    steps: Iterable[StepSnapshot],
) -> tuple[StepSnapshot, ...]:
    items = tuple(steps)

    if not items:
        raise WorkflowError(
            "Workflow must contain at least one step."
        )

    if len(items) > 10:
        raise WorkflowError(
            "Workflow exceeds the 10-step limit."
        )

    by_id: dict[UUID, StepSnapshot] = {}

    for step in items:
        if step.id in by_id:
            raise WorkflowError(
                "Duplicate step ID."
            )

        by_id[step.id] = step

        if len(step.depends_on) != len(
            set(step.depends_on)
        ):
            raise WorkflowError(
                "Duplicate dependency."
            )

        if (
            step.kind == "request_file_approval"
            and not step.requires_approval
        ):
            raise WorkflowError(
                "File approval step requires approval."
            )

        if (
            step.requires_approval
            and step.kind != "request_file_approval"
        ):
            raise WorkflowError(
                "Unsupported approval-gated step."
            )

    visiting: set[UUID] = set()
    visited: set[UUID] = set()

    def visit(step_id: UUID) -> None:
        if step_id in visiting:
            raise WorkflowError(
                "Circular dependency."
            )

        if step_id in visited:
            return

        visiting.add(step_id)

        step = by_id[step_id]

        for dependency in step.depends_on:
            if dependency not in by_id:
                raise WorkflowError(
                    "Unknown dependency."
                )

            if dependency == step_id:
                raise WorkflowError(
                    "Self-dependency is forbidden."
                )

            visit(dependency)

        visiting.remove(step_id)
        visited.add(step_id)

    for step in items:
        visit(step.id)

    return items


def dependencies_completed(
    step: StepSnapshot,
    steps: Iterable[StepSnapshot],
) -> bool:
    items = validate_steps(steps)

    by_id = {
        item.id: item
        for item in items
    }

    if step.id not in by_id:
        raise WorkflowError(
            "Step does not belong to workflow."
        )

    return all(
        by_id[dependency].status
        == StepStatus.COMPLETED
        for dependency in step.depends_on
    )


def derive_workflow_status(
    steps: Iterable[StepSnapshot],
) -> WorkflowStatus:
    items = validate_steps(steps)

    statuses = {
        step.status
        for step in items
    }

    if StepStatus.FAILED in statuses:
        return WorkflowStatus.FAILED

    if StepStatus.CANCELLED in statuses:
        return WorkflowStatus.CANCELLED

    if all(
        step.status == StepStatus.COMPLETED
        for step in items
    ):
        return WorkflowStatus.COMPLETED

    if StepStatus.AWAITING_APPROVAL in statuses:
        return WorkflowStatus.AWAITING_APPROVAL

    if StepStatus.RUNNING in statuses:
        return WorkflowStatus.RUNNING

    if StepStatus.COMPLETED in statuses:
        return WorkflowStatus.RUNNING

    return WorkflowStatus.PLANNED


def transition_step(
    *,
    step_id: UUID,
    event: StepEvent,
    steps: Iterable[StepSnapshot],
    approval_verified: bool = False,
    execution_verified: bool = False,
) -> TransitionResult:
    """Validate a single step transition.

    approval_verified must come from the server-side
    approval service, never from the request body.

    execution_verified must come from trusted server-side
    execution evidence, never from the request body.

    The caller must persist the transition atomically.
    """

    items = validate_steps(steps)

    by_id = {
        step.id: step
        for step in items
    }

    step = by_id.get(step_id)

    if step is None:
        raise WorkflowError(
            "Step not found."
        )

    previous = step.status

    if previous in {
        StepStatus.COMPLETED,
        StepStatus.FAILED,
        StepStatus.CANCELLED,
    }:
        raise WorkflowError(
            "Terminal step cannot transition."
        )

    if event == StepEvent.START:
        if previous != StepStatus.PENDING:
            raise WorkflowError(
                "Only pending steps can start."
            )

        if not dependencies_completed(
            step,
            items,
        ):
            raise WorkflowError(
                "Dependencies are not completed."
            )

        if step.requires_approval:
            raise WorkflowError(
                "Approval-gated steps cannot start directly."
            )

        next_status = StepStatus.RUNNING

    elif event == StepEvent.REQUEST_APPROVAL:
        if previous != StepStatus.PENDING:
            raise WorkflowError(
                "Approval request requires pending status."
            )

        if not step.requires_approval:
            raise WorkflowError(
                "This step does not require approval."
            )

        if not dependencies_completed(
            step,
            items,
        ):
            raise WorkflowError(
                "Dependencies are not completed."
            )

        next_status = StepStatus.AWAITING_APPROVAL

    elif event == StepEvent.APPROVAL_GRANTED:
        if previous != StepStatus.AWAITING_APPROVAL:
            raise WorkflowError(
                "Step is not awaiting approval."
            )

        if not step.requires_approval:
            raise WorkflowError(
                "Step is not approval-gated."
            )

        if not approval_verified:
            raise WorkflowError(
                "Server-side approval verification required."
            )

        next_status = StepStatus.RUNNING

    elif event == StepEvent.APPROVAL_REJECTED:
        if previous != StepStatus.AWAITING_APPROVAL:
            raise WorkflowError(
                "Step is not awaiting approval."
            )

        if not approval_verified:
            raise WorkflowError(
                "Server-side rejection verification required."
            )

        next_status = StepStatus.CANCELLED

    elif event == StepEvent.COMPLETE:
        if previous != StepStatus.RUNNING:
            raise WorkflowError(
                "Only running steps can complete."
            )

        if not execution_verified:
            raise WorkflowError(
                "Trusted execution evidence required."
            )

        next_status = StepStatus.COMPLETED

    elif event == StepEvent.FAIL:
        if previous != StepStatus.RUNNING:
            raise WorkflowError(
                "Only running steps can fail."
            )

        next_status = StepStatus.FAILED

    elif event == StepEvent.CANCEL:
        if previous not in {
            StepStatus.PENDING,
            StepStatus.RUNNING,
            StepStatus.AWAITING_APPROVAL,
        }:
            raise WorkflowError(
                "Step cannot be cancelled."
            )

        next_status = StepStatus.CANCELLED

    else:
        raise WorkflowError(
            "Unsupported step event."
        )

    updated = tuple(
        StepSnapshot(
            id=item.id,
            kind=item.kind,
            status=(
                next_status
                if item.id == step_id
                else item.status
            ),
            depends_on=item.depends_on,
            requires_approval=item.requires_approval,
        )
        for item in items
    )

    return TransitionResult(
        step_id=step_id,
        previous_status=previous,
        next_status=next_status,
        workflow_status=derive_workflow_status(
            updated
        ),
    )
