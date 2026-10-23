
"""Authenticated multilingual planning endpoint."""

from __future__ import annotations

import logging

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
)
from pydantic import BaseModel, Field

from app.api.dependencies import (
    get_current_user,
)
from app.models.user import User

from app.services.multilingual_file_planner import (
    PlannerUnavailableError,
    multilingual_file_planner,
)

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/agent/planning",
    tags=["Agent Planning"],
)


class MultilingualPlanRequest(BaseModel):
    message: str = Field(
        min_length=1,
        max_length=8192,
    )


class MultilingualPlanResponse(BaseModel):
    action: str
    tool_name: str | None = None
    filename: str | None = None
    content: str | None = None
    reason: str
    requires_approval: bool = False


@router.post(
    "/multilingual-file",
    response_model=MultilingualPlanResponse,
)
async def plan_multilingual_file(
    payload: MultilingualPlanRequest,
    current_user: User = Depends(
        get_current_user
    ),
) -> MultilingualPlanResponse:
    # This endpoint creates proposals only.
    # It cannot execute any file operation.
    _ = current_user

    try:
        plan = await multilingual_file_planner.plan(
            payload.message
        )

    except ValueError as exc:
        logger.warning(
            "Invalid multilingual file proposal: %s",
            type(exc).__name__,
        )

        raise HTTPException(
            status_code=422,
            detail=(
                "ORVYN rejected an invalid file proposal."
            ),
        ) from exc

    except PlannerUnavailableError as exc:
        logger.warning(
            "Gemini planner unavailable."
        )

        raise HTTPException(
            status_code=503,
            detail=(
                "Gemini planning is temporarily "
                "unavailable. Please try again later."
            ),
            headers={
                "Retry-After": "30",
            },
        ) from exc

    except Exception as exc:
        logger.exception(
            "Unexpected multilingual planner error."
        )

        raise HTTPException(
            status_code=503,
            detail=(
                "AI planning is temporarily unavailable."
            ),
        ) from exc

    return MultilingualPlanResponse(
        **plan.to_dict()
    )
