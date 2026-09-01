from pathlib import Path

from fastapi import (
    APIRouter,
    Depends,
    File,
    Response,
    UploadFile,
    status,
)
from fastapi.responses import (
    FileResponse,
)
from sqlalchemy.ext.asyncio import (
    AsyncSession,
)

from app.api.dependencies import (
    get_current_user,
)
from app.db.session import get_db
from app.models.user import User
from app.schemas.attachment import (
    AttachmentResponse,
)
from app.services.attachment_service import (
    get_owned_attachment,
    remove_attachment,
    save_attachments,
)


router = APIRouter(
    prefix="/attachments",
    tags=["Attachments"],
)


@router.post(
    "",
    response_model=list[
        AttachmentResponse
    ],
    status_code=(
        status.HTTP_201_CREATED
    ),
)
async def upload_attachments(
    files: list[UploadFile] = File(
        ...
    ),
    current_user: User = Depends(
        get_current_user
    ),
    db: AsyncSession = Depends(
        get_db
    ),
) -> list[AttachmentResponse]:
    attachments = (
        await save_attachments(
            db=db,
            user_id=(
                current_user.id
            ),
            files=files,
        )
    )

    return [
        AttachmentResponse.model_validate(
            attachment
        )
        for attachment
        in attachments
    ]


@router.get(
    "/{attachment_id}",
)
async def get_attachment(
    attachment_id: str,
    current_user: User = Depends(
        get_current_user
    ),
    db: AsyncSession = Depends(
        get_db
    ),
) -> FileResponse:
    attachment = (
        await get_owned_attachment(
            db=db,
            attachment_id=(
                attachment_id
            ),
            user_id=(
                current_user.id
            ),
        )
    )

    path = Path(
        attachment.storage_path
    )

    if not path.is_file():
        from fastapi import HTTPException

        raise HTTPException(
            status_code=(
                status.HTTP_404_NOT_FOUND
            ),
            detail=(
                "Attachment file is unavailable."
            ),
        )

    return FileResponse(
        path=path,
        media_type=(
            attachment.mime_type
        ),
    )


@router.delete(
    "/{attachment_id}",
    status_code=(
        status.HTTP_204_NO_CONTENT
    ),
)
async def delete_attachment(
    attachment_id: str,
    current_user: User = Depends(
        get_current_user
    ),
    db: AsyncSession = Depends(
        get_db
    ),
) -> Response:
    attachment = (
        await get_owned_attachment(
            db=db,
            attachment_id=(
                attachment_id
            ),
            user_id=(
                current_user.id
            ),
        )
    )

    await remove_attachment(
        db=db,
        attachment=attachment,
    )

    return Response(
        status_code=(
            status.HTTP_204_NO_CONTENT
        )
    )