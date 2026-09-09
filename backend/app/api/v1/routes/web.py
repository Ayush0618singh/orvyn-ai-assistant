import logging

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    status,
)

from app.api.dependencies import (
    get_current_user,
)
from app.models.user import (
    User,
)
from app.schemas.web import (
    WebSearchRequest,
    WebSearchResponse,
)
from app.schemas.web_routing import (
    WebNeedDecisionRequest,
    WebNeedDecisionResponse,
)
from app.services.web_need_service import (
    web_need_service,
)
from app.services.web_search_service import (
    web_search_service,
)


logger = logging.getLogger(
    __name__
)


router = APIRouter(
    prefix="/web",
    tags=["Web"],
)


@router.post(
    "/decision",
    response_model=(
        WebNeedDecisionResponse
    ),
    status_code=(
        status.HTTP_200_OK
    ),
)
async def decide_web_need(
    request: WebNeedDecisionRequest,
    current_user: User = Depends(
        get_current_user
    ),
) -> WebNeedDecisionResponse:
    _ = current_user

    return web_need_service.decide(
        message=request.message,
        web_allowed=request.web_allowed,
    )


@router.post(
    "/search",
    response_model=(
        WebSearchResponse
    ),
    status_code=(
        status.HTTP_200_OK
    ),
)
async def search_web(
    request: WebSearchRequest,
    current_user: User = Depends(
        get_current_user
    ),
) -> WebSearchResponse:
    _ = current_user

    try:
        return (
            await web_search_service
            .search(
                query=request.query,
                max_results=(
                    request.max_results
                ),
            )
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    except RuntimeError as exc:
        logger.warning(
            "ORVYN web search failed: %s",
            exc,
        )

        raise HTTPException(
            status_code=503,
            detail=str(exc),
        ) from exc

    except Exception as exc:
        logger.exception(
            "Unexpected ORVYN web search error"
        )

        raise HTTPException(
            status_code=502,
            detail=(
                "Unable to complete "
                "the web search."
            ),
        ) from exc