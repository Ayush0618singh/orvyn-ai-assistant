
"""Tests for persisted workflow snapshot conversion."""

from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.agent_orchestration.state_machine import (
    StepStatus,
    WorkflowError,
    validate_steps,
)
from app.services.agent_workflow_service import (
    build_snapshots,
)


def make_record(
    *,
    step_id=None,
    kind="prepare_content",
    status="pending",
    depends_on=None,
    requires_approval=False,
):
    return SimpleNamespace(
        id=str(step_id or uuid4()),
        kind=kind,
        status=status,
        depends_on=(
            depends_on
            if depends_on is not None
            else []
        ),
        requires_approval=requires_approval,
    )


def test_empty_snapshot_conversion():
    assert build_snapshots([]) == ()


def test_valid_snapshot_conversion():
    record = make_record()

    snapshots = build_snapshots(
        [record]
    )

    assert len(snapshots) == 1
    assert snapshots[0].status == (
        StepStatus.PENDING
    )


def test_dependencies_are_preserved():
    first = make_record()

    second = make_record(
        kind="summarize",
        depends_on=[first.id],
    )

    snapshots = build_snapshots(
        [first, second]
    )

    assert snapshots[1].depends_on == (
        snapshots[0].id,
    )


def test_approval_requirement_preserved():
    record = make_record(
        kind="request_file_approval",
        requires_approval=True,
    )

    snapshots = build_snapshots(
        [record]
    )

    assert (
        snapshots[0].requires_approval
        is True
    )


def test_invalid_step_uuid_rejected():
    record = make_record()
    record.id = "invalid"

    with pytest.raises(
        WorkflowError,
        match="invalid data",
    ):
        build_snapshots([record])


def test_invalid_dependency_uuid_rejected():
    record = make_record(
        depends_on=["not-a-uuid"]
    )

    with pytest.raises(
        WorkflowError,
        match="invalid data",
    ):
        build_snapshots([record])


def test_invalid_status_rejected():
    record = make_record(
        status="approved_without_check"
    )

    with pytest.raises(
        WorkflowError,
        match="invalid data",
    ):
        build_snapshots([record])


def test_duplicate_steps_rejected_by_validator():
    record = make_record()

    snapshots = build_snapshots(
        [record, record]
    )

    with pytest.raises(
        WorkflowError,
        match="Duplicate step ID",
    ):
        validate_steps(snapshots)


def test_unknown_dependency_rejected():
    record = make_record(
        depends_on=[str(uuid4())]
    )

    snapshots = build_snapshots(
        [record]
    )

    with pytest.raises(
        WorkflowError,
        match="Unknown dependency",
    ):
        validate_steps(snapshots)


def test_unapproved_file_step_rejected():
    record = make_record(
        kind="request_file_approval",
        requires_approval=False,
    )

    snapshots = build_snapshots(
        [record]
    )

    with pytest.raises(
        WorkflowError,
        match="requires approval",
    ):
        validate_steps(snapshots)
