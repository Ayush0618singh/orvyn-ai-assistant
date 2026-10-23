
"""Conversation-linked tool approval API for ORVYN.

Security:
- Explicit Bearer authentication for approval creation.
- Conversation ownership checks.
- Message-to-conversation ownership checks.
- No tool execution in this router.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
)
from pydantic import (
    BaseModel,
    ConfigDict,
)
from sqlalchemy import (
    func,
    select,
)
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user
from app.api.v1.routes.tool_approvals import (
    WORKSPACE_TOOL_NAME,
    get_explicit_bearer_user,
)
from app.db.session import get_db

from app.models.chat_tool_approval_link import (
    ChatToolApprovalLink,
)
from app.models.conversation import Conversation
from app.models.message import Message
from app.models.tool_approval_record import (
    ToolApprovalRecord,
)
from app.models.user import User

from app.schemas.durable_tool_approval_api import (
    ToolApprovalListResponse,
    ToolApprovalResponse,
)
from app.schemas.tool import ToolCallRequest

from app.services.agent_approval_workflow_service import (
    create_agent_approval_workflow,
)
from app.services.agent_tool_approval_service import (
    AgentToolApprovalError,
)

from app.tools.builtin.workspace_file_write import (
    WorkspaceFileWriteInput,
)
from app.tools.enums import ToolPermission
from app.tools.executor import create_execution_context


router = APIRouter(
    prefix="/chat-tool-approvals",
    tags=["Chat Tool Approvals"],
)


class ChatWorkspaceFileRequest(
    WorkspaceFileWriteInput
):
    model_config = ConfigDict(
        extra="forbid"
    )

    conversation_id: UUID
    message_id: UUID | None = None


class ApprovalMessageLinkResponse(BaseModel):
    approval_id: str
    conversation_id: str
    message_id: str | None


class ApprovalMessageLinksResponse(BaseModel):
    items: list[ApprovalMessageLinkResponse]
    total: int


async def get_owned_conversation_or_404(
    db: AsyncSession,
    *,
    conversation_id: UUID,
    user_id: UUID,
) -> Conversation:
    result = await db.execute(
        select(Conversation).where(
            Conversation.id == str(conversation_id),
            Conversation.user_id == str(user_id),
        )
    )

    conversation = result.scalar_one_or_none()

    if conversation is None:
        raise HTTPException(
            status_code=404,
            detail="Conversation not found.",
        )

    return conversation


async def verify_owned_user_message(
    db: AsyncSession,
    *,
    message_id: UUID,
    conversation_id: UUID,
    user_id: UUID,
) -> None:
    result = await db.execute(
        select(Message.id)
        .join(
            Conversation,
            Message.conversation_id == Conversation.id,
        )
        .where(
            Message.id == str(message_id),
            Message.conversation_id == str(conversation_id),
            Conversation.id == str(conversation_id),
            Conversation.user_id == str(user_id),
            Message.role == "user",
            Message.status == "completed",
        )
    )

    if result.scalar_one_or_none() is None:
        raise HTTPException(
            status_code=404,
            detail="User message not found.",
        )


@router.post(
    "/workspace-file",
    response_model=ToolApprovalResponse,
    status_code=201,
)
async def request_chat_workspace_file(
    payload: ChatWorkspaceFileRequest,
    current_user: User = Depends(
        get_explicit_bearer_user
    ),
    db: AsyncSession = Depends(get_db),
) -> ToolApprovalResponse:
    user_id = UUID(str(current_user.id))

    await get_owned_conversation_or_404(
        db,
        conversation_id=payload.conversation_id,
        user_id=user_id,
    )

    if payload.message_id is not None:
        await verify_owned_user_message(
            db,
            message_id=payload.message_id,
            conversation_id=payload.conversation_id,
            user_id=user_id,
        )

    # Only validated file arguments reach the tool.
    tool_arguments = WorkspaceFileWriteInput(
        filename=payload.filename,
        content=payload.content,
    ).model_dump(mode="json")

    request = ToolCallRequest(
        tool_name=WORKSPACE_TOOL_NAME,
        arguments=tool_arguments,
    )

    context = create_execution_context(
        user_id=user_id,
        granted_permissions=[
            ToolPermission.FILE_WRITE
        ],
    )

    workflow = create_agent_approval_workflow()

    try:
        result = await workflow.request_approval(
            db=db,
            request=request,
            context=context,
            ttl_seconds=300,
        )
    except AgentToolApprovalError:
        raise HTTPException(
            status_code=400,
            detail="Approval could not be created.",
        ) from None

    link = ChatToolApprovalLink(
        approval_id=str(result.approval_id),
        conversation_id=str(payload.conversation_id),
        user_id=str(user_id),
        message_id=(
            str(payload.message_id)
            if payload.message_id is not None
            else None
        ),
    )

    try:
        db.add(link)
        await db.commit()
    except Exception:
        await db.rollback()

        raise HTTPException(
            status_code=500,
            detail=(
                "Approval was created but could not "
                "be linked to the conversation."
            ),
        ) from None

    record_result = await db.execute(
        select(ToolApprovalRecord).where(
            ToolApprovalRecord.id == str(result.approval_id),
            ToolApprovalRecord.user_id == str(user_id),
        )
    )

    record = record_result.scalar_one_or_none()

    if record is None:
        raise HTTPException(
            status_code=500,
            detail="Created approval could not be loaded.",
        )

    return ToolApprovalResponse.model_validate(
        record
    )


@router.get(
    "/conversations/{conversation_id}",
    response_model=ToolApprovalListResponse,
)
async def list_conversation_approvals(
    conversation_id: UUID,
    current_user: User = Depends(
        get_current_user
    ),
    db: AsyncSession = Depends(get_db),
    limit: int = Query(
        default=100,
        ge=1,
        le=100,
    ),
    offset: int = Query(
        default=0,
        ge=0,
    ),
) -> ToolApprovalListResponse:
    user_id = UUID(str(current_user.id))

    await get_owned_conversation_or_404(
        db,
        conversation_id=conversation_id,
        user_id=user_id,
    )

    filters = (
        ChatToolApprovalLink.user_id == str(user_id),
        ChatToolApprovalLink.conversation_id
        == str(conversation_id),
        ToolApprovalRecord.user_id == str(user_id),
    )

    count_result = await db.execute(
        select(func.count(ToolApprovalRecord.id))
        .select_from(ChatToolApprovalLink)
        .join(
            ToolApprovalRecord,
            ToolApprovalRecord.id
            == ChatToolApprovalLink.approval_id,
        )
        .where(*filters)
    )

    result = await db.execute(
        select(ToolApprovalRecord)
        .join(
            ChatToolApprovalLink,
            ChatToolApprovalLink.approval_id
            == ToolApprovalRecord.id,
        )
        .where(*filters)
        .order_by(
            ChatToolApprovalLink.created_at.asc(),
            ToolApprovalRecord.id.asc(),
        )
        .limit(limit)
        .offset(offset)
    )

    return ToolApprovalListResponse(
        items=[
            ToolApprovalResponse.model_validate(
                record
            )
            for record in result.scalars().all()
        ],
        total=count_result.scalar_one(),
        limit=limit,
        offset=offset,
    )


@router.get(
    "/conversations/{conversation_id}/message-links",
    response_model=ApprovalMessageLinksResponse,
)
async def list_approval_message_links(
    conversation_id: UUID,
    current_user: User = Depends(
        get_current_user
    ),
    db: AsyncSession = Depends(get_db),
) -> ApprovalMessageLinksResponse:
    user_id = UUID(str(current_user.id))

    await get_owned_conversation_or_404(
        db,
        conversation_id=conversation_id,
        user_id=user_id,
    )

    result = await db.execute(
        select(ChatToolApprovalLink)
        .join(
            ToolApprovalRecord,
            ToolApprovalRecord.id
            == ChatToolApprovalLink.approval_id,
        )
        .where(
            ChatToolApprovalLink.user_id == str(user_id),
            ChatToolApprovalLink.conversation_id
            == str(conversation_id),
            ToolApprovalRecord.user_id == str(user_id),
        )
        .order_by(
            ChatToolApprovalLink.created_at.asc(),
            ChatToolApprovalLink.approval_id.asc(),
        )
    )

    links = list(result.scalars().all())

    return ApprovalMessageLinksResponse(
        items=[
            ApprovalMessageLinkResponse(
                approval_id=link.approval_id,
                conversation_id=link.conversation_id,
                message_id=link.message_id,
            )
            for link in links
        ],
        total=len(links),
    )
