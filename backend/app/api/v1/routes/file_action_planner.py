
"""Authenticated, read-only file action planning API."""

from __future__ import annotations

from fastapi import (
    APIRouter,
    Depends,
)
from pydantic import (
    BaseModel,
    Field,
)

from app.api.dependencies import get_current_user
from app.models.user import User
from app.services.file_action_planner import (
    plan_file_action,
)

router = APIRouter(
    prefix="/agent/planning",
    tags=["Agent Planning"],
)


class FilePlanRequest(BaseModel):
    message: str = Field(
        min_length=1,
        max_length=8192,
    )


class FilePlanResponse(BaseModel):
    recognized: bool
    tool_name: str | None = None
    filename: str | None = None
    content: str | None = None
    requires_approval: bool = False
    message: str


@router.post(
    "/file",
    response_model=FilePlanResponse,
)
async def plan_file_request(
    payload: FilePlanRequest,
    current_user: User = Depends(
        get_current_user
    ),
) -> FilePlanResponse:
    # Authentication is enforced by dependency.
    # No database mutation or tool execution occurs.
    _ = current_user

    proposal = plan_file_action(
        payload.message
    )

    if proposal is None:
        return FilePlanResponse(
            recognized=False,
            message=(
                "File action not recognized. "
                "Specify a .txt filename and exact content."
            ),
        )

    return FilePlanResponse(
        recognized=True,
        tool_name=proposal.tool_name,
        filename=proposal.filename,
        content=proposal.content,
        requires_approval=True,
        message=(
            "File action proposed. "
            "Explicit approval and separate execution "
            "are required."
        ),
    )
