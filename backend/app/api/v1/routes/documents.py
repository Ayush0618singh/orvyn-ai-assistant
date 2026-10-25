
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.document import (
    DocumentDetailResponse,
    DocumentResponse,
)
from app.services.document_extraction_service import (
    DocumentExtractionError,
)
from app.services.document_service import document_service


logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/documents",
    tags=["Documents"],
)


@router.post(
    "/from-attachment/{attachment_id}",
    response_model=DocumentDetailResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_document_from_attachment(
    attachment_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> DocumentDetailResponse:
    try:
        return await document_service.ingest_attachment(
            db=db,
            user_id=current_user.id,
            attachment_id=attachment_id,
        )
    except ValueError as exc:
        message = str(exc)

        if message == "Attachment not found.":
            code = status.HTTP_404_NOT_FOUND
        elif message == "This document is already being processed.":
            code = status.HTTP_409_CONFLICT
        else:
            code = status.HTTP_400_BAD_REQUEST

        raise HTTPException(
            status_code=code,
            detail=message,
        ) from exc

    except DocumentExtractionError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc

    except Exception as exc:
        logger.exception(
            "Document ingestion failed for user %s and attachment %s",
            current_user.id,
            attachment_id,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Document indexing failed. Please try again later.",
        ) from exc


@router.get(
    "",
    response_model=list[DocumentResponse],
)
async def list_documents(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[DocumentResponse]:
    return await document_service.get_documents(
        db=db,
        user_id=current_user.id,
    )


@router.get(
    "/{document_id}",
    response_model=DocumentDetailResponse,
)
async def get_document(
    document_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> DocumentDetailResponse:
    try:
        return await document_service.get_owned_document(
            db=db,
            user_id=current_user.id,
            document_id=document_id,
            include_chunks=True,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found.",
        ) from exc


@router.delete(
    "/{document_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_document(
    document_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    try:
        await document_service.delete_document(
            db=db,
            user_id=current_user.id,
            document_id=document_id,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found.",
        ) from exc
