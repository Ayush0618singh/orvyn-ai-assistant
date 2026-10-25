
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.config import settings
from app.services.document_service import DocumentService


def make_result(value):
    """Create a mock SQLAlchemy result object."""
    result = MagicMock()
    result.scalar_one_or_none.return_value = value
    return result


@pytest.mark.asyncio
async def test_ingestion_rejects_missing_attachment():
    db = AsyncMock()
    db.execute.return_value = make_result(None)

    with pytest.raises(ValueError, match="Attachment not found"):
        await DocumentService().ingest_attachment(
            db=db,
            user_id="user-1",
            attachment_id="missing-attachment",
        )

    db.execute.assert_awaited_once()
    db.add.assert_not_called()
    db.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_ingestion_rejects_unsupported_mime_type():
    attachment = SimpleNamespace(
        id="attachment-1",
        user_id="user-1",
        mime_type="application/octet-stream",
        original_name="archive.bin",
        stored_name="archive.bin",
        size_bytes=100,
        storage_path="not-used.bin",
    )

    db = AsyncMock()
    db.execute.return_value = make_result(attachment)

    with pytest.raises(ValueError, match="Only PDF and TXT"):
        await DocumentService().ingest_attachment(
            db=db,
            user_id="user-1",
            attachment_id="attachment-1",
        )

    db.add.assert_not_called()
    db.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_missing_attachment_file_is_not_marked_ready(
    tmp_path,
):
    user_id = "user-1"
    stored_name = "missing-notes-file.txt"

    # Match the real storage layout:
    # upload_dir / user_id / stored_name
    expected_path = (
        tmp_path / user_id / stored_name
    )

    attachment = SimpleNamespace(
        id="attachment-1",
        user_id=user_id,
        mime_type="text/plain",
        original_name="notes.txt",
        stored_name=stored_name,
        size_bytes=20,
        storage_path=str(expected_path),
    )

    document = SimpleNamespace(
        id="document-1",
        user_id=user_id,
        attachment_id="attachment-1",
        name="notes.txt",
        mime_type="text/plain",
        size_bytes=20,
        status="processing",
        error_message=None,
        extracted_text=None,
    )

    db = AsyncMock()
    db.add = MagicMock()
    db.delete = MagicMock()

    db.execute.side_effect = [
        make_result(attachment),
        make_result(None),
        make_result(document),
    ]

    async def refresh(obj):
        obj.id = "document-1"

    db.refresh.side_effect = refresh

    with (
        patch.object(
            settings,
            "upload_dir",
            tmp_path,
        ),
        patch.object(
            Path,
            "is_file",
            return_value=False,
        ),
    ):
        with pytest.raises(
            Exception,
            match="attachment file is missing",
        ):
            await DocumentService().ingest_attachment(
                db=db,
                user_id=user_id,
                attachment_id="attachment-1",
            )

    assert document.status == "failed"
    assert document.error_message is not None
    assert "DocumentExtractionError" in document.error_message
    db.rollback.assert_awaited()
