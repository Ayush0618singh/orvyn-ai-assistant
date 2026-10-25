
from __future__ import annotations

import asyncio
import logging
import uuid
from pathlib import Path

from fastapi import HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.types import AIAttachment
from app.core.config import settings
from app.core.storage_security import (
    UnsafeStoragePathError,
    resolve_existing_storage_path,
    resolve_storage_file,
    resolve_user_storage_dir,
)
from app.models.attachment import Attachment


logger = logging.getLogger(__name__)

SUPPORTED_TYPES = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "application/pdf": ".pdf",
    "text/plain": ".txt",
}


def _detect_mime_type(filename: str, data: bytes) -> tuple[str, str]:
    suffix = Path(filename.replace("\\", "/")).suffix.lower()

    if data.startswith(b"\xff\xd8\xff") and suffix in {".jpg", ".jpeg"}:
        return "image/jpeg", ".jpg"

    if data.startswith(b"\x89PNG\r\n\x1a\n") and suffix == ".png":
        return "image/png", ".png"

    if (
        len(data) >= 12
        and data[:4] == b"RIFF"
        and data[8:12] == b"WEBP"
        and suffix == ".webp"
    ):
        return "image/webp", ".webp"

    if data.startswith(b"%PDF-") and suffix == ".pdf":
        return "application/pdf", ".pdf"

    if suffix == ".txt":
        try:
            data.decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Text files must use UTF-8 encoding.",
            ) from exc

        if b"\x00" in data:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid text file.",
            )

        return "text/plain", ".txt"

    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Unsupported file. Allowed: JPG, JPEG, PNG, WEBP, PDF and TXT.",
    )


async def _close_uploads(files: list[UploadFile]) -> None:
    for upload in files:
        try:
            await upload.close()
        except Exception:
            logger.warning("Could not close an uploaded file handle.")


async def _cleanup_created_files(paths: list[Path]) -> None:
    for path in paths:
        try:
            await asyncio.to_thread(path.unlink, missing_ok=True)
        except OSError:
            logger.exception("Could not clean up a partially uploaded file.")


async def save_attachments(
    db: AsyncSession,
    *,
    user_id: str,
    files: list[UploadFile],
) -> list[Attachment]:
    """Validate and store uploaded files in the authenticated user's directory."""
    if not isinstance(user_id, str) or not user_id.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid user identifier.",
        )

    if not files:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No files were selected.",
        )

    max_count = settings.max_attachments_per_message
    if len(files) > max_count:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Too many attachments. Maximum {max_count} files are allowed.",
        )

    max_size = settings.max_upload_size_mb * 1024 * 1024
    created_files: list[Path] = []
    attachments: list[Attachment] = []

    try:
        user_directory = resolve_user_storage_dir(settings.upload_dir, user_id)

        await asyncio.to_thread(
            user_directory.mkdir,
            parents=True,
            exist_ok=True,
        )

        # Re-resolve after directory creation to catch unexpected path changes.
        verified_directory = resolve_user_storage_dir(
            settings.upload_dir,
            user_id,
        )
        if verified_directory != user_directory or user_directory.is_symlink():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Attachment storage directory failed security validation.",
            )

        for upload in files:
            raw_name = (upload.filename or "attachment").replace("\\", "/")
            original_name = Path(raw_name).name[:255] or "attachment"

            data = await upload.read(max_size + 1)

            if not data:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"{original_name} is empty.",
                )

            if len(data) > max_size:
                raise HTTPException(
                    status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    detail=(
                        f"{original_name} exceeds "
                        f"{settings.max_upload_size_mb} MB."
                    ),
                )

            mime_type, extension = _detect_mime_type(original_name, data)
            stored_name = f"{uuid.uuid4().hex}{extension}"

            file_path = resolve_storage_file(
                settings.upload_dir,
                user_id,
                stored_name,
            )

            if file_path.exists() or file_path.is_symlink():
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Could not safely allocate attachment storage.",
                )

            created_files.append(file_path)
            await asyncio.to_thread(file_path.write_bytes, data)

            attachment = Attachment(
                user_id=user_id,
                original_name=original_name,
                stored_name=stored_name,
                mime_type=mime_type,
                size_bytes=len(data),
                storage_path=str(file_path),
            )
            db.add(attachment)
            attachments.append(attachment)

        await db.commit()

        for attachment in attachments:
            await db.refresh(attachment)

        return attachments

    except Exception:
        try:
            await db.rollback()
        except Exception:
            logger.exception(
                "Database rollback failed after attachment upload error."
            )

        await _cleanup_created_files(created_files)
        raise

    finally:
        await _close_uploads(files)


async def get_owned_attachment(
    db: AsyncSession,
    *,
    attachment_id: str,
    user_id: str,
) -> Attachment:
    result = await db.execute(
        select(Attachment).where(
            Attachment.id == attachment_id,
            Attachment.user_id == user_id,
        )
    )
    attachment = result.scalar_one_or_none()

    if attachment is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Attachment not found.",
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

    if len(set(attachment_ids)) != len(attachment_ids):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Duplicate attachment IDs are not allowed.",
        )

    result = await db.execute(
        select(Attachment).where(
            Attachment.id.in_(attachment_ids),
            Attachment.user_id == user_id,
        )
    )
    found = list(result.scalars().all())
    by_id = {attachment.id: attachment for attachment in found}

    if len(by_id) != len(attachment_ids):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="One or more attachments were not found.",
        )

    ordered = [by_id[attachment_id] for attachment_id in attachment_ids]

    for attachment in ordered:
        if (
            attachment.message_id is not None
            or attachment.conversation_id is not None
        ):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="An attachment has already been used.",
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

    try:
        for attachment in attachments:
            if (
                attachment.message_id is not None
                or attachment.conversation_id is not None
            ):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="An attachment has already been used.",
                )

            attachment.conversation_id = conversation_id
            attachment.message_id = message_id

        await db.commit()

    except Exception:
        await db.rollback()
        raise


async def build_ai_attachments(
    attachments: list[Attachment],
) -> list[AIAttachment]:
    result: list[AIAttachment] = []

    for attachment in attachments:
        try:
            path = resolve_existing_storage_path(
                settings.upload_dir,
                attachment.user_id,
                attachment.stored_name,
                attachment.storage_path,
            )
        except UnsafeStoragePathError as exc:
            logger.error(
                "Unsafe storage path rejected for attachment %s.",
                attachment.id,
            )
            raise RuntimeError(
                "Attachment storage path failed security validation."
            ) from exc

        if path.is_symlink() or not path.is_file():
            raise RuntimeError("Attachment file is missing or unsafe.")

        data = await asyncio.to_thread(path.read_bytes)

        if len(data) != attachment.size_bytes:
            raise RuntimeError(
                "Attachment size does not match its database record."
            )

        result.append(
            AIAttachment(
                filename=attachment.original_name,
                mime_type=attachment.mime_type,
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
        attachment.message_id is not None
        or attachment.conversation_id is not None
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "An attachment already used in a conversation "
                "cannot be removed separately."
            ),
        )

    try:
        path = resolve_existing_storage_path(
            settings.upload_dir,
            attachment.user_id,
            attachment.stored_name,
            attachment.storage_path,
        )
    except UnsafeStoragePathError as exc:
        logger.error(
            "Refusing to delete attachment %s due to unsafe storage path.",
            attachment.id,
        )
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Attachment storage path failed security validation.",
        ) from exc

    await db.delete(attachment)
    await db.commit()

    try:
        await asyncio.to_thread(path.unlink, missing_ok=True)
    except OSError:
        logger.exception(
            "Attachment record %s was deleted, but its file could not be removed.",
            attachment.id,
        )


async def remove_conversation_files(
    db: AsyncSession,
    *,
    conversation_id: str,
    user_id: str,
) -> None:
    result = await db.execute(
        select(Attachment).where(
            Attachment.conversation_id == conversation_id,
            Attachment.user_id == user_id,
        )
    )
    attachments = list(result.scalars().all())

    for attachment in attachments:
        try:
            path = resolve_existing_storage_path(
                settings.upload_dir,
                attachment.user_id,
                attachment.stored_name,
                attachment.storage_path,
            )
        except UnsafeStoragePathError:
            logger.error(
                "Skipping unsafe attachment path for attachment %s.",
                attachment.id,
            )
            continue

        try:
            await asyncio.to_thread(path.unlink, missing_ok=True)
        except OSError:
            logger.exception(
                "Could not remove attachment file for attachment %s.",
                attachment.id,
            )
