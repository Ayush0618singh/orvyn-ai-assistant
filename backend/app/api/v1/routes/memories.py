from fastapi import (
    APIRouter,
    Depends,
    Query,
    Response,
    status,
)
from sqlalchemy.ext.asyncio import (
    AsyncSession,
)

from app.api.dependencies import (
    get_current_user,
)
from app.db.session import get_db
from app.models.user import (
    User,
)
from app.schemas.memory import (
    ALLOWED_MEMORY_TYPES,
    MemoryCreate,
    MemoryResponse,
    MemorySearchRequest,
    MemorySearchResult,
    MemoryUpdate,
)
from app.services.memory_service import (
    memory_service,
)


router = APIRouter(
    prefix="/memories",
    tags=["Memory"],
)


@router.post(
    "",
    response_model=MemoryResponse,
    status_code=(
        status.HTTP_201_CREATED
    ),
)
async def create_memory(
    payload: MemoryCreate,
    current_user: User = Depends(
        get_current_user
    ),
    db: AsyncSession = Depends(
        get_db
    ),
) -> MemoryResponse:
    return (
        await memory_service
        .create_memory(
            db=db,
            user_id=(
                current_user.id
            ),
            payload=payload,
        )
    )


@router.get(
    "",
    response_model=list[
        MemoryResponse
    ],
)
async def list_memories(
    memory_type: (
        str | None
    ) = Query(
        default=None
    ),
    active_only: bool = Query(
        default=True
    ),
    current_user: User = Depends(
        get_current_user
    ),
    db: AsyncSession = Depends(
        get_db
    ),
) -> list[MemoryResponse]:
    if memory_type:
        memory_type = (
            memory_type
            .lower()
            .strip()
        )

        if (
            memory_type
            not in ALLOWED_MEMORY_TYPES
        ):
            from fastapi import (
                HTTPException,
            )

            raise HTTPException(
                status_code=400,
                detail=(
                    "Unsupported memory type."
                ),
            )

    return (
        await memory_service
        .list_memories(
            db=db,
            user_id=(
                current_user.id
            ),
            memory_type=(
                memory_type
            ),
            active_only=(
                active_only
            ),
        )
    )


@router.post(
    "/search",
    response_model=list[
        MemorySearchResult
    ],
)
async def search_memories(
    payload: MemorySearchRequest,
    current_user: User = Depends(
        get_current_user
    ),
    db: AsyncSession = Depends(
        get_db
    ),
) -> list[MemorySearchResult]:
    results = (
        await memory_service
        .search_memories(
            db=db,
            user_id=(
                current_user.id
            ),
            payload=payload,
        )
    )

    return [
        MemorySearchResult(
            **item
        )
        for item in results
    ]


@router.get(
    "/{memory_id}",
    response_model=MemoryResponse,
)
async def get_memory(
    memory_id: str,
    current_user: User = Depends(
        get_current_user
    ),
    db: AsyncSession = Depends(
        get_db
    ),
) -> MemoryResponse:
    return (
        await memory_service
        .get_memory(
            db=db,
            user_id=(
                current_user.id
            ),
            memory_id=(
                memory_id
            ),
        )
    )


@router.patch(
    "/{memory_id}",
    response_model=MemoryResponse,
)
async def update_memory(
    memory_id: str,
    payload: MemoryUpdate,
    current_user: User = Depends(
        get_current_user
    ),
    db: AsyncSession = Depends(
        get_db
    ),
) -> MemoryResponse:
    return (
        await memory_service
        .update_memory(
            db=db,
            user_id=(
                current_user.id
            ),
            memory_id=(
                memory_id
            ),
            payload=payload,
        )
    )


@router.delete(
    "/{memory_id}",
    status_code=(
        status.HTTP_204_NO_CONTENT
    ),
)
async def delete_memory(
    memory_id: str,
    current_user: User = Depends(
        get_current_user
    ),
    db: AsyncSession = Depends(
        get_db
    ),
) -> Response:
    await memory_service.delete_memory(
        db=db,
        user_id=(
            current_user.id
        ),
        memory_id=(
            memory_id
        ),
    )

    return Response(
        status_code=(
            status.HTTP_204_NO_CONTENT
        )
    )