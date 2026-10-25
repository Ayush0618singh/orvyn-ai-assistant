
from __future__ import annotations

import logging

from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    Response,
    UploadFile,
    status,
)
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user
from app.core.config import settings
from app.core.storage_security import (
    UnsafeStoragePathError,
    resolve_existing_storage_path,
)
from app.db.session import get_db
from app.models.user import User
from app.schemas.attachment import AttachmentResponse
from app.services.attachment_service import (
    get_owned_attachment,
    remove_attachment,
    save_attachments,
)

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/attachments",
    tags=["Attachments"],
)


@router.post(
    "",
    response_model=list[AttachmentResponse],
    status_code=status.HTTP_201_CREATED,
)
async def upload_attachments(
    files: list[UploadFile] = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[AttachmentResponse]:
    try:
        attachments = await save_attachments(
            db=db,
            user_id=current_user.id,
            files=files,
        )
        return [
            AttachmentResponse.model_validate(attachment)
            for attachment in attachments
        ]
    except HTTPException:
        raise
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        logger.exception(
            "Attachment upload failed for user %s",
            current_user.id,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Attachment upload failed.",
        ) from exc


@router.get("/{attachment_id}")
async def get_attachment(
    attachment_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> FileResponse:
    attachment = await get_owned_attachment(
        db=db,
        attachment_id=attachment_id,
        user_id=current_user.id,
    )

    try:
        path = resolve_existing_storage_path(
            settings.upload_dir,
            attachment.user_id,
            attachment.stored_name,
            attachment.storage_path,
        )
    except UnsafeStoragePathError as exc:
        logger.warning(
            "Rejected unsafe download path for attachment %s.",
            attachment.id,
        )
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Attachment storage path failed security validation.",
        ) from exc

    if path.is_symlink() or not path.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Attachment file is unavailable.",
        )

    safe_filename = attachment.original_name.replace("\\", "/").split("/")[-1]
    safe_filename = safe_filename or "download"

    return FileResponse(
        path=path,
        media_type=attachment.mime_type or "application/octet-stream",
        filename=safe_filename,
        content_disposition_type="attachment",
        headers={"X-Content-Type-Options": "nosniff"},
    )


@router.delete(
    "/{attachment_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_attachment(
    attachment_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Response:
    attachment = await get_owned_attachment(
        db=db,
        attachment_id=attachment_id,
        user_id=current_user.id,
    )

    await remove_attachment(
        db=db,
        attachment=attachment,
    )

    return Response(
        status_code=status.HTTP_204_NO_CONTENT,
    )
