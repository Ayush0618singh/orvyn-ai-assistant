from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from datetime import (
    UTC,
    datetime,
    timedelta,
)
from typing import Any
from uuid import (
    UUID,
    uuid4,
)

from app.schemas.tool_approval import (
    ToolApprovalDecision,
    ToolApprovalRequest,
    ToolApprovalVerification,
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


DEFAULT_APPROVAL_TTL_SECONDS = 300

MAX_APPROVAL_TTL_SECONDS = 900


def canonicalize_tool_arguments(
    arguments: dict[str, Any],
) -> str:
    """
    Convert tool arguments into deterministic JSON.

    Approval binding uses this canonical representation so
    argument order cannot change the digest.
    """

    return json.dumps(
        arguments,
        sort_keys=True,
        separators=(
            ",",
            ":",
        ),
        ensure_ascii=False,
        allow_nan=False,
    )


def calculate_arguments_digest(
    arguments: dict[str, Any],
) -> str:
    """
    SHA-256 digest used to bind an approval to the exact
    tool arguments approved by the user.
    """

    canonical = (
        canonicalize_tool_arguments(
            arguments
        )
    )

    return hashlib.sha256(
        canonical.encode(
            "utf-8"
        )
    ).hexdigest()


class InMemoryToolApprovalStore:
    """
    Development/testing approval store.

    Important:
    This is intentionally process-local and must not be used
    as ORVYN's final production approval persistence layer.

    Phase 10I will replace the storage implementation while
    keeping the approval security contract.
    """

    def __init__(self) -> None:
        self._approvals: dict[
            UUID,
            ToolApprovalRequest,
        ] = {}

    def save(
        self,
        approval: ToolApprovalRequest,
    ) -> ToolApprovalRequest:
        self._approvals[
            approval.approval_id
        ] = approval.model_copy(
            deep=True
        )

        return approval.model_copy(
            deep=True
        )

    def get(
        self,
        approval_id: UUID,
    ) -> ToolApprovalRequest:
        approval = self._approvals.get(
            approval_id
        )

        if approval is None:
            raise ToolApprovalNotFoundError(
                (
                    f"Approval '{approval_id}' "
                    f"was not found."
                )
            )

        return approval.model_copy(
            deep=True
        )

    def update(
        self,
        approval: ToolApprovalRequest,
    ) -> ToolApprovalRequest:
        if (
            approval.approval_id
            not in self._approvals
        ):
            raise ToolApprovalNotFoundError(
                (
                    f"Approval "
                    f"'{approval.approval_id}' "
                    f"was not found."
                )
            )

        self._approvals[
            approval.approval_id
        ] = approval.model_copy(
            deep=True
        )

        return approval.model_copy(
            deep=True
        )


class ToolApprovalService:
    """
    ORVYN approval workflow.

    Approval is bound to:
    - one authenticated user,
    - one exact tool name,
    - one exact argument payload,
    - one expiry period.

    Approved requests are one-time consumable.
    """

    def __init__(
        self,
        store: InMemoryToolApprovalStore
        | None = None,
    ) -> None:
        self._store = (
            store
            or InMemoryToolApprovalStore()
        )

    def create_request(
        self,
        *,
        user_id: UUID,
        tool_name: str,
        arguments: dict[str, Any],
        risk_level: ToolRiskLevel,
        ttl_seconds: int = (
            DEFAULT_APPROVAL_TTL_SECONDS
        ),
        now: datetime | None = None,
    ) -> ToolApprovalRequest:
        if ttl_seconds < 1:
            raise ValueError(
                (
                    "Approval TTL must be "
                    "at least one second."
                )
            )

        if (
            ttl_seconds
            > MAX_APPROVAL_TTL_SECONDS
        ):
            raise ValueError(
                (
                    "Approval TTL cannot exceed "
                    f"{MAX_APPROVAL_TTL_SECONDS} "
                    "seconds."
                )
            )

        current_time = (
            now
            or datetime.now(
                UTC
            )
        )

        safe_arguments = deepcopy(
            arguments
        )

        approval = ToolApprovalRequest(
            approval_id=uuid4(),
            user_id=user_id,
            tool_name=tool_name,
            arguments=safe_arguments,
            arguments_digest=(
                calculate_arguments_digest(
                    safe_arguments
                )
            ),
            risk_level=risk_level,
            status=(
                ToolApprovalStatus.PENDING
            ),
            created_at=current_time,
            expires_at=(
                current_time
                + timedelta(
                    seconds=ttl_seconds
                )
            ),
        )

        return self._store.save(
            approval
        )

    def get_request(
        self,
        *,
        approval_id: UUID,
        now: datetime | None = None,
    ) -> ToolApprovalRequest:
        approval = self._store.get(
            approval_id
        )

        return self._expire_if_needed(
            approval=approval,
            now=now,
        )

    def approve(
        self,
        *,
        approval_id: UUID,
        user_id: UUID,
        now: datetime | None = None,
    ) -> ToolApprovalDecision:
        approval = self.get_request(
            approval_id=approval_id,
            now=now,
        )

        self._verify_user(
            approval=approval,
            user_id=user_id,
        )

        if (
            approval.status
            == ToolApprovalStatus.EXPIRED
        ):
            raise ToolApprovalExpiredError(
                "Approval request has expired."
            )

        if (
            approval.status
            == ToolApprovalStatus.DENIED
        ):
            raise ToolApprovalDeniedError(
                "Approval request was denied."
            )

        if (
            approval.status
            == ToolApprovalStatus.CONSUMED
        ):
            raise ToolApprovalConsumedError(
                (
                    "Approval request has "
                    "already been consumed."
                )
            )

        current_time = (
            now
            or datetime.now(
                UTC
            )
        )

        approval.status = (
            ToolApprovalStatus.APPROVED
        )

        approval.decided_at = (
            current_time
        )

        self._store.update(
            approval
        )

        return ToolApprovalDecision(
            approval_id=(
                approval.approval_id
            ),
            status=(
                approval.status
            ),
            decided_at=current_time,
        )

    def deny(
        self,
        *,
        approval_id: UUID,
        user_id: UUID,
        now: datetime | None = None,
    ) -> ToolApprovalDecision:
        approval = self.get_request(
            approval_id=approval_id,
            now=now,
        )

        self._verify_user(
            approval=approval,
            user_id=user_id,
        )

        if (
            approval.status
            == ToolApprovalStatus.EXPIRED
        ):
            raise ToolApprovalExpiredError(
                "Approval request has expired."
            )

        if (
            approval.status
            == ToolApprovalStatus.CONSUMED
        ):
            raise ToolApprovalConsumedError(
                (
                    "Consumed approval cannot "
                    "be denied."
                )
            )

        current_time = (
            now
            or datetime.now(
                UTC
            )
        )

        approval.status = (
            ToolApprovalStatus.DENIED
        )

        approval.decided_at = (
            current_time
        )

        self._store.update(
            approval
        )

        return ToolApprovalDecision(
            approval_id=(
                approval.approval_id
            ),
            status=(
                approval.status
            ),
            decided_at=current_time,
        )

    def verify_and_consume(
        self,
        *,
        approval_id: UUID,
        user_id: UUID,
        tool_name: str,
        arguments: dict[str, Any],
        now: datetime | None = None,
    ) -> ToolApprovalVerification:
        approval = self.get_request(
            approval_id=approval_id,
            now=now,
        )

        self._verify_user(
            approval=approval,
            user_id=user_id,
        )

        if (
            approval.status
            == ToolApprovalStatus.EXPIRED
        ):
            raise ToolApprovalExpiredError(
                "Approval request has expired."
            )

        if (
            approval.status
            == ToolApprovalStatus.DENIED
        ):
            raise ToolApprovalDeniedError(
                "Approval request was denied."
            )

        if (
            approval.status
            == ToolApprovalStatus.CONSUMED
        ):
            raise ToolApprovalConsumedError(
                (
                    "Approval request has "
                    "already been consumed."
                )
            )

        if (
            approval.status
            != ToolApprovalStatus.APPROVED
        ):
            raise ToolApprovalMismatchError(
                (
                    "Approval request has not "
                    "been approved."
                )
            )

        if (
            approval.tool_name
            != tool_name
        ):
            raise ToolApprovalMismatchError(
                (
                    "Approval does not match "
                    "the requested tool."
                )
            )

        supplied_digest = (
            calculate_arguments_digest(
                arguments
            )
        )

        if (
            supplied_digest
            != approval.arguments_digest
        ):
            raise ToolApprovalMismatchError(
                (
                    "Approval does not match "
                    "the requested arguments."
                )
            )

        current_time = (
            now
            or datetime.now(
                UTC
            )
        )

        approval.status = (
            ToolApprovalStatus.CONSUMED
        )

        approval.consumed_at = (
            current_time
        )

        self._store.update(
            approval
        )

        return ToolApprovalVerification(
            approval_id=(
                approval.approval_id
            ),
            verified=True,
            consumed=True,
        )

    def _expire_if_needed(
        self,
        *,
        approval: ToolApprovalRequest,
        now: datetime | None,
    ) -> ToolApprovalRequest:
        current_time = (
            now
            or datetime.now(
                UTC
            )
        )

        if (
            approval.status
            in {
                ToolApprovalStatus.PENDING,
                ToolApprovalStatus.APPROVED,
            }
            and current_time
            >= approval.expires_at
        ):
            approval.status = (
                ToolApprovalStatus.EXPIRED
            )

            self._store.update(
                approval
            )

        return approval

    @staticmethod
    def _verify_user(
        *,
        approval: ToolApprovalRequest,
        user_id: UUID,
    ) -> None:
        if (
            approval.user_id
            != user_id
        ):
            raise ToolApprovalMismatchError(
                (
                    "Approval does not belong "
                    "to this user."
                )
            )