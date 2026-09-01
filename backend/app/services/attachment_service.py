import asyncio
import uuid
from pathlib import Path

from fastapi import (
    HTTPException,
    UploadFile,
    status,
)
from sqlalchemy import (
    select,
)
from sqlalchemy.ext.asyncio import (
    AsyncSession,
)

from app.ai.types import (
    AIAttachment,
)
from app.core.config import settings
from app.models.attachment import (
    Attachment,
)


SUPPORTED_TYPES = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "application/pdf": ".pdf",
    "text/plain": ".txt",
}


def _detect_mime_type(
    filename: str,
    data: bytes,
) -> tuple[str, str]:
    suffix = (
        Path(filename)
        .suffix
        .lower()
    )

    if (
        data.startswith(
            b"\xff\xd8\xff"
        )
        and suffix
        in {
            ".jpg",
            ".jpeg",
        }
    ):
        return (
            "image/jpeg",
            ".jpg",
        )

    if (
        data.startswith(
            b"\x89PNG\r\n\x1a\n"
        )
        and suffix == ".png"
    ):
        return (
            "image/png",
            ".png",
        )

    if (
        len(data) >= 12
        and data[:4] == b"RIFF"
        and data[8:12]
        == b"WEBP"
        and suffix == ".webp"
    ):
        return (
            "image/webp",
            ".webp",
        )

    if (
        data.startswith(
            b"%PDF-"
        )
        and suffix == ".pdf"
    ):
        return (
            "application/pdf",
            ".pdf",
        )

    if suffix == ".txt":
        try:
            data.decode(
                "utf-8"
            )
        except UnicodeDecodeError as exc:
            raise HTTPException(
                status_code=(
                    status.HTTP_400_BAD_REQUEST
                ),
                detail=(
                    "Text files must use UTF-8 encoding."
                ),
            ) from exc

        if b"\x00" in data:
            raise HTTPException(
                status_code=(
                    status.HTTP_400_BAD_REQUEST
                ),
                detail=(
                    "Invalid text file."
                ),
            )

        return (
            "text/plain",
            ".txt",
        )

    raise HTTPException(
        status_code=(
            status.HTTP_400_BAD_REQUEST
        ),
        detail=(
            "Unsupported file. "
            "Allowed: JPG, JPEG, PNG, WEBP, PDF and TXT."
        ),
    )


async def save_attachments(
    db: AsyncSession,
    *,
    user_id: str,
    files: list[UploadFile],
) -> list[Attachment]:
    if not files:
        raise HTTPException(
            status_code=(
                status.HTTP_400_BAD_REQUEST
            ),
            detail=(
                "No files were selected."
            ),
        )

    if (
        len(files)
        > settings.max_attachments_per_message
    ):
        raise HTTPException(
            status_code=(
                status.HTTP_400_BAD_REQUEST
            ),
            detail=(
                "Too many attachments. "
                f"Maximum {settings.max_attachments_per_message} "
                "files are allowed."
            ),
        )

    max_size = (
        settings.max_upload_size_mb
        * 1024
        * 1024
    )

    upload_root = Path(
        settings.upload_dir
    ).resolve()

    user_directory = (
        upload_root
        / user_id
    )

    user_directory.mkdir(
        parents=True,
        exist_ok=True,
    )

    created_files: list[
        Path
    ] = []

    attachments: list[
        Attachment
    ] = []

    try:
        for upload in files:
            original_name = (
                Path(
                    upload.filename
                    or "attachment"
                )
                .name
            )

            data = await upload.read(
                max_size + 1
            )

            await upload.close()

            if not data:
                raise HTTPException(
                    status_code=(
                        status.HTTP_400_BAD_REQUEST
                    ),
                    detail=(
                        f"{original_name} is empty."
                    ),
                )

            if len(data) > max_size:
                raise HTTPException(
                    status_code=(
                        status.HTTP_413_REQUEST_ENTITY_TOO_LARGE
                    ),
                    detail=(
                        f"{original_name} exceeds "
                        f"{settings.max_upload_size_mb} MB."
                    ),
                )

            (
                mime_type,
                extension,
            ) = _detect_mime_type(
                original_name,
                data,
            )

            stored_name = (
                f"{uuid.uuid4()}"
                f"{extension}"
            )

            file_path = (
                user_directory
                / stored_name
            )

            await asyncio.to_thread(
                file_path.write_bytes,
                data,
            )

            created_files.append(
                file_path
            )

            attachment = Attachment(
                user_id=user_id,
                original_name=(
                    original_name[:255]
                ),
                stored_name=(
                    stored_name
                ),
                mime_type=mime_type,
                size_bytes=len(data),
                storage_path=str(
                    file_path
                ),
            )

            db.add(
                attachment
            )

            attachments.append(
                attachment
            )

        await db.commit()

        for attachment in attachments:
            await db.refresh(
                attachment
            )

        return attachments

    except Exception:
        await db.rollback()

        for file_path in created_files:
            try:
                await asyncio.to_thread(
                    file_path.unlink,
                    missing_ok=True,
                )
            except OSError:
                pass

        raise


async def get_owned_attachment(
    db: AsyncSession,
    *,
    attachment_id: str,
    user_id: str,
) -> Attachment:
    result = await db.execute(
        select(
            Attachment
        ).where(
            Attachment.id
            == attachment_id,
            Attachment.user_id
            == user_id,
        )
    )

    attachment = (
        result.scalar_one_or_none()
    )

    if not attachment:
        raise HTTPException(
            status_code=(
                status.HTTP_404_NOT_FOUND
            ),
            detail=(
                "Attachment not found."
            ),
        )

    return attachment


async def get_pending_attachments(
    db: AsyncSession,
    *,
    attachment_ids: list[str],
    user_id: str,
) -> list[Attachment]:
    if not attachment_ids:
        return []

    result = await db.execute(
        select(
            Attachment
        ).where(
            Attachment.id.in_(
                attachment_ids
            ),
            Attachment.user_id
            == user_id,
        )
    )

    found = list(
        result.scalars().all()
    )

    by_id = {
        attachment.id:
            attachment
        for attachment in found
    }

    if len(by_id) != len(
        attachment_ids
    ):
        raise HTTPException(
            status_code=(
                status.HTTP_404_NOT_FOUND
            ),
            detail=(
                "One or more attachments were not found."
            ),
        )

    ordered = [
        by_id[
            attachment_id
        ]
        for attachment_id
        in attachment_ids
    ]

    for attachment in ordered:
        if (
            attachment.message_id
            is not None
            or attachment.conversation_id
            is not None
        ):
            raise HTTPException(
                status_code=(
                    status.HTTP_409_CONFLICT
                ),
                detail=(
                    "An attachment has already been used."
                ),
            )

    return ordered


async def bind_attachments(
    db: AsyncSession,
    *,
    attachments: list[Attachment],
    conversation_id: str,
    message_id: str,
) -> None:
    if not attachments:
        return

    for attachment in attachments:
        attachment.conversation_id = (
            conversation_id
        )

        attachment.message_id = (
            message_id
        )

    await db.commit()


async def build_ai_attachments(
    attachments: list[Attachment],
) -> list[AIAttachment]:
    result: list[
        AIAttachment
    ] = []

    for attachment in attachments:
        path = Path(
            attachment.storage_path
        )

        if not path.is_file():
            raise RuntimeError(
                "Attachment file is missing from storage."
            )

        data = await asyncio.to_thread(
            path.read_bytes
        )

        result.append(
            AIAttachment(
                filename=(
                    attachment.original_name
                ),
                mime_type=(
                    attachment.mime_type
                ),
                data=data,
            )
        )

    return result


async def remove_attachment(
    db: AsyncSession,
    *,
    attachment: Attachment,
) -> None:
    if (
        attachment.message_id
        is not None
        or attachment.conversation_id
        is not None
    ):
        raise HTTPException(
            status_code=(
                status.HTTP_409_CONFLICT
            ),
            detail=(
                "An attachment already used in a conversation "
                "cannot be removed separately."
            ),
        )

    path = Path(
        attachment.storage_path
    )

    await db.delete(
        attachment
    )

    await db.commit()

    try:
        await asyncio.to_thread(
            path.unlink,
            missing_ok=True,
        )
    except OSError:
        pass


async def remove_conversation_files(
    db: AsyncSession,
    *,
    conversation_id: str,
    user_id: str,
) -> None:
    result = await db.execute(
        select(
            Attachment
        ).where(
            Attachment.conversation_id
            == conversation_id,
            Attachment.user_id
            == user_id,
        )
    )

    attachments = list(
        result.scalars().all()
    )

    for attachment in attachments:
        path = Path(
            attachment.storage_path
        )

        try:
            await asyncio.to_thread(
                path.unlink,
                missing_ok=True,
            )
        except OSError:
            pass