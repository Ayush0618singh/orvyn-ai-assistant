import logging

from fastapi import APIRouter, HTTPException, status

from app.core.config import settings
from app.schemas.chat import ChatRequest, ChatResponse
from app.services.chat_service import get_chat_service


logger = logging.getLogger(__name__)


router = APIRouter(
    prefix="/chat",
    tags=["Chat"],
)


@router.post(
    "",
    response_model=ChatResponse,
    status_code=status.HTTP_200_OK,
)
async def chat(request: ChatRequest) -> ChatResponse:
    try:
        chat_service = get_chat_service()

        response = await chat_service.chat(
            message=request.message,
        )

        return ChatResponse(
            response=response,
            model=settings.llm_model,
            provider=settings.llm_provider,
        )

    except ValueError as exc:
        logger.exception("ORVYN configuration error")

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc

    except Exception as exc:
        logger.exception("ORVYN AI provider request failed")

        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="The AI provider request failed.",
        ) from exc