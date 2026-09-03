from fastapi import (
    APIRouter,
    Depends,
)
from sqlalchemy.ext.asyncio import (
    AsyncSession,
)

from app.api.dependencies import (
    get_current_user,
)
from app.db.session import (
    get_db,
)
from app.models.user import (
    User,
)
from app.schemas.auto_memory import (
    AutoMemoryDecisionRequest,
    AutoMemoryDecisionResponse,
    AutoMemoryEvaluateRequest,
    AutoMemoryEvaluateResponse,
    AutoMemoryExtractRequest,
    AutoMemoryExtractResponse,
    AutoMemoryProcessRequest,
    AutoMemoryProcessResponse,
    AutoMemorySettingsResponse,
    AutoMemorySettingsUpdate,
)
from app.services.auto_memory_decision_service import (
    auto_memory_decision_service,
)
from app.services.auto_memory_extractor_service import (
    auto_memory_extractor_service,
)
from app.services.auto_memory_persistence_service import (
    auto_memory_persistence_service,
)
from app.services.auto_memory_service import (
    auto_memory_service,
)
from app.services.auto_memory_settings_service import (
    auto_memory_settings_service,
)


router = APIRouter(
    prefix="/auto-memory",
    tags=["Auto Memory"],
)


@router.get(
    "/settings",
    response_model=(
        AutoMemorySettingsResponse
    ),
)
async def get_auto_memory_settings(
    current_user: User = Depends(
        get_current_user
    ),
) -> AutoMemorySettingsResponse:
    enabled = (
        await auto_memory_settings_service
        .get_settings(
            user=current_user,
        )
    )

    return AutoMemorySettingsResponse(
        auto_memory_enabled=enabled,
    )


@router.patch(
    "/settings",
    response_model=(
        AutoMemorySettingsResponse
    ),
)
async def update_auto_memory_settings(
    payload: AutoMemorySettingsUpdate,
    db: AsyncSession = Depends(
        get_db
    ),
    current_user: User = Depends(
        get_current_user
    ),
) -> AutoMemorySettingsResponse:
    enabled = (
        await auto_memory_settings_service
        .update_settings(
            db=db,
            user=current_user,
            auto_memory_enabled=(
                payload.auto_memory_enabled
            ),
        )
    )

    return AutoMemorySettingsResponse(
        auto_memory_enabled=enabled,
    )


@router.post(
    "/evaluate",
    response_model=(
        AutoMemoryEvaluateResponse
    ),
)
async def evaluate_auto_memory(
    payload: AutoMemoryEvaluateRequest,
    current_user: User = Depends(
        get_current_user
    ),
) -> AutoMemoryEvaluateResponse:
    _ = current_user

    candidate = (
        auto_memory_service
        .evaluate_message(
            payload.message
        )
    )

    return AutoMemoryEvaluateResponse(
        candidate=candidate
    )


@router.post(
    "/extract",
    response_model=(
        AutoMemoryExtractResponse
    ),
)
async def extract_auto_memory(
    payload: AutoMemoryExtractRequest,
    current_user: User = Depends(
        get_current_user
    ),
) -> AutoMemoryExtractResponse:
    _ = current_user

    candidate = (
        await auto_memory_extractor_service
        .extract_candidate(
            payload.message
        )
    )

    return AutoMemoryExtractResponse(
        candidate=candidate
    )


@router.post(
    "/decision",
    response_model=(
        AutoMemoryDecisionResponse
    ),
)
async def decide_auto_memory(
    payload: AutoMemoryDecisionRequest,
    db: AsyncSession = Depends(
        get_db
    ),
    current_user: User = Depends(
        get_current_user
    ),
) -> AutoMemoryDecisionResponse:
    decision = (
        await auto_memory_decision_service
        .decide(
            db=db,
            user=current_user,
            user_message=(
                payload.message
            ),
        )
    )

    return AutoMemoryDecisionResponse(
        decision=decision
    )


@router.post(
    "/process",
    response_model=(
        AutoMemoryProcessResponse
    ),
)
async def process_auto_memory(
    payload: AutoMemoryProcessRequest,
    db: AsyncSession = Depends(
        get_db
    ),
    current_user: User = Depends(
        get_current_user
    ),
) -> AutoMemoryProcessResponse:
    result = (
        await auto_memory_persistence_service
        .process(
            db=db,
            user=current_user,
            user_message=(
                payload.message
            ),
            source_message_id=None,
        )
    )

    return AutoMemoryProcessResponse(
        result=result
    )