from datetime import (
    UTC,
    datetime,
    timedelta,
)
from uuid import uuid4

import pytest

from app.tools.approval import (
    InMemoryToolApprovalStore,
    ToolApprovalService,
    calculate_arguments_digest,
    canonicalize_tool_arguments,
)
from app.tools.enums import (
    ToolApprovalStatus,
    ToolRiskLevel,
)
from app.tools.exceptions import (
    ToolApprovalConsumedError,
    ToolApprovalDeniedError,
    ToolApprovalExpiredError,
    ToolApprovalMismatchError,
    ToolApprovalNotFoundError,
)


@pytest.fixture
def service():
    return ToolApprovalService(
        store=(
            InMemoryToolApprovalStore()
        )
    )


def test_argument_digest_is_order_independent():
    first = {
        "b": 2,
        "a": 1,
    }

    second = {
        "a": 1,
        "b": 2,
    }

    assert (
        calculate_arguments_digest(
            first
        )
        ==
        calculate_arguments_digest(
            second
        )
    )


def test_argument_digest_changes_when_value_changes():
    first = {
        "amount": 100,
    }

    second = {
        "amount": 101,
    }

    assert (
        calculate_arguments_digest(
            first
        )
        !=
        calculate_arguments_digest(
            second
        )
    )


def test_canonical_json_is_deterministic():
    assert (
        canonicalize_tool_arguments(
            {
                "z": 1,
                "a": 2,
            }
        )
        ==
        '{"a":2,"z":1}'
    )


def test_create_approval_request(
    service: ToolApprovalService,
):
    user_id = uuid4()

    approval = (
        service.create_request(
            user_id=user_id,
            tool_name="email_send",
            arguments={
                "to": "user@example.com",
            },
            risk_level=(
                ToolRiskLevel.HIGH
            ),
        )
    )

    assert (
        approval.user_id
        == user_id
    )

    assert (
        approval.tool_name
        == "email_send"
    )

    assert (
        approval.status
        == ToolApprovalStatus.PENDING
    )

    assert (
        len(
            approval.arguments_digest
        )
        == 64
    )


def test_approve_request(
    service: ToolApprovalService,
):
    user_id = uuid4()

    approval = (
        service.create_request(
            user_id=user_id,
            tool_name="email_send",
            arguments={
                "to": "user@example.com",
            },
            risk_level=(
                ToolRiskLevel.HIGH
            ),
        )
    )

    decision = service.approve(
        approval_id=(
            approval.approval_id
        ),
        user_id=user_id,
    )

    assert (
        decision.status
        == ToolApprovalStatus.APPROVED
    )


def test_deny_request(
    service: ToolApprovalService,
):
    user_id = uuid4()

    approval = (
        service.create_request(
            user_id=user_id,
            tool_name="email_send",
            arguments={
                "to": "user@example.com",
            },
            risk_level=(
                ToolRiskLevel.HIGH
            ),
        )
    )

    decision = service.deny(
        approval_id=(
            approval.approval_id
        ),
        user_id=user_id,
    )

    assert (
        decision.status
        == ToolApprovalStatus.DENIED
    )


def test_verified_approval_is_consumed_once(
    service: ToolApprovalService,
):
    user_id = uuid4()

    arguments = {
        "to": "user@example.com",
        "subject": "Hello",
    }

    approval = (
        service.create_request(
            user_id=user_id,
            tool_name="email_send",
            arguments=arguments,
            risk_level=(
                ToolRiskLevel.HIGH
            ),
        )
    )

    service.approve(
        approval_id=(
            approval.approval_id
        ),
        user_id=user_id,
    )

    verification = (
        service.verify_and_consume(
            approval_id=(
                approval.approval_id
            ),
            user_id=user_id,
            tool_name="email_send",
            arguments=arguments,
        )
    )

    assert (
        verification.verified
        is True
    )

    assert (
        verification.consumed
        is True
    )

    with pytest.raises(
        ToolApprovalConsumedError
    ):
        service.verify_and_consume(
            approval_id=(
                approval.approval_id
            ),
            user_id=user_id,
            tool_name="email_send",
            arguments=arguments,
        )


def test_approval_cannot_be_used_by_another_user(
    service: ToolApprovalService,
):
    owner_id = uuid4()

    other_user_id = uuid4()

    arguments = {
        "path": "notes.txt",
    }

    approval = (
        service.create_request(
            user_id=owner_id,
            tool_name="file_write",
            arguments=arguments,
            risk_level=(
                ToolRiskLevel.HIGH
            ),
        )
    )

    service.approve(
        approval_id=(
            approval.approval_id
        ),
        user_id=owner_id,
    )

    with pytest.raises(
        ToolApprovalMismatchError
    ):
        service.verify_and_consume(
            approval_id=(
                approval.approval_id
            ),
            user_id=other_user_id,
            tool_name="file_write",
            arguments=arguments,
        )


def test_approval_cannot_be_reused_for_another_tool(
    service: ToolApprovalService,
):
    user_id = uuid4()

    arguments = {
        "value": "hello",
    }

    approval = (
        service.create_request(
            user_id=user_id,
            tool_name="tool_one",
            arguments=arguments,
            risk_level=(
                ToolRiskLevel.HIGH
            ),
        )
    )

    service.approve(
        approval_id=(
            approval.approval_id
        ),
        user_id=user_id,
    )

    with pytest.raises(
        ToolApprovalMismatchError
    ):
        service.verify_and_consume(
            approval_id=(
                approval.approval_id
            ),
            user_id=user_id,
            tool_name="tool_two",
            arguments=arguments,
        )


def test_approval_cannot_be_reused_for_changed_arguments(
    service: ToolApprovalService,
):
    user_id = uuid4()

    approved_arguments = {
        "to": "friend@example.com",
    }

    changed_arguments = {
        "to": "attacker@example.com",
    }

    approval = (
        service.create_request(
            user_id=user_id,
            tool_name="email_send",
            arguments=(
                approved_arguments
            ),
            risk_level=(
                ToolRiskLevel.HIGH
            ),
        )
    )

    service.approve(
        approval_id=(
            approval.approval_id
        ),
        user_id=user_id,
    )

    with pytest.raises(
        ToolApprovalMismatchError
    ):
        service.verify_and_consume(
            approval_id=(
                approval.approval_id
            ),
            user_id=user_id,
            tool_name="email_send",
            arguments=(
                changed_arguments
            ),
        )


def test_pending_approval_cannot_execute(
    service: ToolApprovalService,
):
    user_id = uuid4()

    arguments = {
        "value": 1,
    }

    approval = (
        service.create_request(
            user_id=user_id,
            tool_name="dangerous_tool",
            arguments=arguments,
            risk_level=(
                ToolRiskLevel.HIGH
            ),
        )
    )

    with pytest.raises(
        ToolApprovalMismatchError
    ):
        service.verify_and_consume(
            approval_id=(
                approval.approval_id
            ),
            user_id=user_id,
            tool_name="dangerous_tool",
            arguments=arguments,
        )


def test_denied_approval_cannot_execute(
    service: ToolApprovalService,
):
    user_id = uuid4()

    arguments = {
        "value": 1,
    }

    approval = (
        service.create_request(
            user_id=user_id,
            tool_name="dangerous_tool",
            arguments=arguments,
            risk_level=(
                ToolRiskLevel.HIGH
            ),
        )
    )

    service.deny(
        approval_id=(
            approval.approval_id
        ),
        user_id=user_id,
    )

    with pytest.raises(
        ToolApprovalDeniedError
    ):
        service.verify_and_consume(
            approval_id=(
                approval.approval_id
            ),
            user_id=user_id,
            tool_name="dangerous_tool",
            arguments=arguments,
        )


def test_approval_expires(
    service: ToolApprovalService,
):
    user_id = uuid4()

    created_at = datetime(
        2026,
        9,
        9,
        12,
        0,
        tzinfo=UTC,
    )

    approval = (
        service.create_request(
            user_id=user_id,
            tool_name="email_send",
            arguments={
                "to": "user@example.com",
            },
            risk_level=(
                ToolRiskLevel.HIGH
            ),
            ttl_seconds=60,
            now=created_at,
        )
    )

    with pytest.raises(
        ToolApprovalExpiredError
    ):
        service.approve(
            approval_id=(
                approval.approval_id
            ),
            user_id=user_id,
            now=(
                created_at
                + timedelta(
                    seconds=61
                )
            ),
        )


def test_unknown_approval_rejected(
    service: ToolApprovalService,
):
    with pytest.raises(
        ToolApprovalNotFoundError
    ):
        service.get_request(
            approval_id=uuid4()
        )


@pytest.mark.parametrize(
    "ttl",
    [
        0,
        -1,
        901,
        5000,
    ],
)
def test_invalid_ttl_rejected(
    service: ToolApprovalService,
    ttl: int,
):
    with pytest.raises(
        ValueError
    ):
        service.create_request(
            user_id=uuid4(),
            tool_name="email_send",
            arguments={},
            risk_level=(
                ToolRiskLevel.HIGH
            ),
            ttl_seconds=ttl,
        )


def test_stored_arguments_are_not_affected_by_external_mutation(
    service: ToolApprovalService,
):
    user_id = uuid4()

    arguments = {
        "recipient": "safe@example.com",
    }

    approval = (
        service.create_request(
            user_id=user_id,
            tool_name="email_send",
            arguments=arguments,
            risk_level=(
                ToolRiskLevel.HIGH
            ),
        )
    )

    arguments[
        "recipient"
    ] = "changed@example.com"

    stored = service.get_request(
        approval_id=(
            approval.approval_id
        )
    )

    assert (
        stored.arguments[
            "recipient"
        ]
        == "safe@example.com"
    )