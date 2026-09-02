from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    status,
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
from app.schemas.document import (
    DocumentDetailResponse,
    DocumentResponse,
)
from app.services.document_service import (
    document_service,
)


router = APIRouter(
    prefix="/documents",
    tags=["Documents"],
)


@router.post(
    "/from-attachment/{attachment_id}",
    response_model=(
        DocumentDetailResponse
    ),
    status_code=(
        status.HTTP_201_CREATED
    ),
)
async def create_document_from_attachment(
    attachment_id: str,
    current_user: User = Depends(
        get_current_user
    ),
    db: AsyncSession = Depends(
        get_db
    ),
):
    try:
        return (
            await document_service
            .ingest_attachment(
                db=db,
                user_id=current_user.id,
                attachment_id=(
                    attachment_id
                ),
            )
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=(
                "Document indexing failed: "
                f"{exc}"
            ),
        ) from exc


@router.get(
    "",
    response_model=list[
        DocumentResponse
    ],
)
async def list_documents(
    current_user: User = Depends(
        get_current_user
    ),
    db: AsyncSession = Depends(
        get_db
    ),
):
    return (
        await document_service
        .get_documents(
            db=db,
            user_id=current_user.id,
        )
    )


@router.get(
    "/{document_id}",
    response_model=(
        DocumentDetailResponse
    ),
)
async def get_document(
    document_id: str,
    current_user: User = Depends(
        get_current_user
    ),
    db: AsyncSession = Depends(
        get_db
    ),
):
    try:
        return (
            await document_service
            .get_owned_document(
                db=db,
                user_id=current_user.id,
                document_id=(
                    document_id
                ),
                include_chunks=True,
            )
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc),
        ) from exc


@router.delete(
    "/{document_id}",
    status_code=(
        status.HTTP_204_NO_CONTENT
    ),
)
async def delete_document(
    document_id: str,
    current_user: User = Depends(
        get_current_user
    ),
    db: AsyncSession = Depends(
        get_db
    ),
):
    try:
        await (
            document_service
            .delete_document(
                db=db,
                user_id=current_user.id,
                document_id=(
                    document_id
                ),
            )
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc),
        ) from exc

    return None