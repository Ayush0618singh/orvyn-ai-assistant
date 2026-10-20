
"""Authenticated and user-isolated durable tool approval API.

Approval creation remains internal to trusted backend services.
Approved execution uses stored arguments and verified audit.
"""

from __future__ import annotations

from uuid import UUID

import jwt
from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
)
from fastapi.security import (
    HTTPAuthorizationCredentials,
    HTTPBearer,
)
from jwt import InvalidTokenError
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user
from app.core.config import settings
from app.db.session import get_db
from app.models.tool_approval_record import ToolApprovalRecord
from app.models.user import User
from app.schemas.durable_tool_approval_api import (
    ToolApprovalDecisionResponse,
    ToolApprovalListResponse,
    ToolApprovalResponse,
)
from app.schemas.tool import ToolExecutionResult
from app.services.agent_approval_execution_service import (
    AgentApprovalExecutionError,
)
from app.services.agent_approval_workflow_service import (
    create_agent_approval_workflow,
)
from app.services.durable_tool_approval_service import (
    ApprovalStateError,
    durable_tool_approval_service,
)


router = APIRouter(
    prefix="/tool-approvals",
    tags=["Tool Approvals"],
)

bearer_scheme = HTTPBearer(auto_error=False)


def parse_approval_id(value: str) -> UUID:
    try:
        return UUID(value)
    except (ValueError, TypeError, AttributeError):
        raise HTTPException(
            status_code=404,
            detail="Tool approval not found.",
        ) from None


def not_found() -> HTTPException:
    return HTTPException(
        status_code=404,
        detail="Tool approval not found.",
    )


def conflict() -> HTTPException:
    return HTTPException(
        status_code=409,
        detail="Approval is no longer pending or has expired.",
    )


async def get_explicit_bearer_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(
        bearer_scheme
    ),
    db: AsyncSession = Depends(get_db),
) -> User:
    """
    Authenticate approval decisions and execution using
    an explicit Bearer token. Never fall back to cookies.
    """

    if (
        credentials is None
        or credentials.scheme.lower() != "bearer"
        or not credentials.credentials
    ):
        raise HTTPException(
            status_code=401,
            detail="A valid Bearer token is required.",
        )

    try:
        payload = jwt.decode(
            credentials.credentials,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
        )

        user_id = payload.get("sub")

        if not isinstance(user_id, str) or not user_id:
            raise ValueError("Missing token subject.")

        normalized_user_id = str(UUID(user_id))

    except (
        InvalidTokenError,
        ValueError,
        TypeError,
        AttributeError,
    ):
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired Bearer token.",
        ) from None

    result = await db.execute(
        select(User).where(
            User.id == normalized_user_id
        )
    )

    user = result.scalar_one_or_none()

    if user is None or not user.is_active:
        raise HTTPException(
            status_code=401,
            detail="User not found or inactive.",
        )

    return user


async def get_owned_approval(
    db: AsyncSession,
    *,
    approval_id: UUID,
    current_user: User,
) -> ToolApprovalRecord:
    try:
        return await durable_tool_approval_service.get(
            db,
            approval_id=approval_id,
            user_id=UUID(str(current_user.id)),
        )
    except ApprovalStateError:
        raise not_found() from None


async def make_decision(
    *,
    db: AsyncSession,
    approval_id: UUID,
    current_user: User,
    approve: bool,
) -> ToolApprovalDecisionResponse:
    await get_owned_approval(
        db,
        approval_id=approval_id,
        current_user=current_user,
    )

    try:
        record = await durable_tool_approval_service.decide(
            db,
            approval_id=approval_id,
            user_id=UUID(str(current_user.id)),
            approve=approve,
        )
    except ApprovalStateError:
        raise conflict() from None

    if record.decided_at is None:
        raise HTTPException(
            status_code=500,
            detail="Approval decision was not recorded.",
        )

    return ToolApprovalDecisionResponse(
        id=UUID(record.id),
        status=record.status,
        decided_at=record.decided_at,
    )


@router.get(
    "",
    response_model=ToolApprovalListResponse,
)
async def list_tool_approvals(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    approval_status: str | None = Query(
        default=None,
        alias="status",
        pattern="^(pending|approved|denied|consumed|expired)$",
    ),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> ToolApprovalListResponse:

    filters = [
        ToolApprovalRecord.user_id == str(current_user.id)
    ]

    if approval_status is not None:
        filters.append(
            ToolApprovalRecord.status == approval_status
        )

    total_result = await db.execute(
        select(func.count(ToolApprovalRecord.id)).where(
            *filters
        )
    )

    result = await db.execute(
        select(ToolApprovalRecord)
        .where(*filters)
        .order_by(
            ToolApprovalRecord.created_at.desc(),
            ToolApprovalRecord.id.desc(),
        )
        .limit(limit)
        .offset(offset)
    )

    return ToolApprovalListResponse(
        items=[
            ToolApprovalResponse.model_validate(record)
            for record in result.scalars().all()
        ],
        total=total_result.scalar_one(),
        limit=limit,
        offset=offset,
    )


@router.get(
    "/{approval_id}",
    response_model=ToolApprovalResponse,
)
async def get_tool_approval(
    approval_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ToolApprovalResponse:

    record = await get_owned_approval(
        db,
        approval_id=parse_approval_id(approval_id),
        current_user=current_user,
    )

    return ToolApprovalResponse.model_validate(record)


@router.post(
    "/{approval_id}/approve",
    response_model=ToolApprovalDecisionResponse,
)
async def approve_tool_request(
    approval_id: str,
    current_user: User = Depends(get_explicit_bearer_user),
    db: AsyncSession = Depends(get_db),
) -> ToolApprovalDecisionResponse:

    return await make_decision(
        db=db,
        approval_id=parse_approval_id(approval_id),
        current_user=current_user,
        approve=True,
    )


@router.post(
    "/{approval_id}/deny",
    response_model=ToolApprovalDecisionResponse,
)
async def deny_tool_request(
    approval_id: str,
    current_user: User = Depends(get_explicit_bearer_user),
    db: AsyncSession = Depends(get_db),
) -> ToolApprovalDecisionResponse:

    return await make_decision(
        db=db,
        approval_id=parse_approval_id(approval_id),
        current_user=current_user,
        approve=False,
    )


@router.post(
    "/{approval_id}/execute",
    response_model=ToolExecutionResult,
)
async def execute_approved_tool_request(
    approval_id: str,
    current_user: User = Depends(get_explicit_bearer_user),
    db: AsyncSession = Depends(get_db),
) -> ToolExecutionResult:
    """
    Explicit execution after a separate approval decision.

    No client-controlled arguments, permissions, user ID,
    approval flag, or execution context are accepted.

    Until a trusted permission resolver is integrated,
    the HTTP endpoint grants no capability permissions.
    Tools requiring capabilities will be denied by the
    verified execution service.
    """

    parsed_id = parse_approval_id(approval_id)

    # Hide approvals belonging to another user.
    await get_owned_approval(
        db,
        approval_id=parsed_id,
        current_user=current_user,
    )

    workflow = create_agent_approval_workflow()

    try:
        return await workflow.execute_approved(
            db=db,
            approval_id=parsed_id,
            user_id=UUID(str(current_user.id)),
            granted_permissions=[],
        )
    except AgentApprovalExecutionError:
        raise HTTPException(
            status_code=409,
            detail=(
                "Approval is unavailable or not approved."
            ),
        ) from None
