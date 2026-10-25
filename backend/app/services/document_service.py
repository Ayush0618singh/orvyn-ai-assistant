
from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.storage_security import (
    UnsafeStoragePathError,
    resolve_existing_storage_path,
)
from app.models.attachment import Attachment
from app.models.document import Document
from app.models.document_chunk import DocumentChunk
from app.services.chunking_service import chunking_service
from app.services.document_extraction_service import (
    DocumentExtractionError,
    document_extraction_service,
)
from app.services.embedding_service import embedding_service


logger = logging.getLogger(__name__)


class DocumentService:
    ALLOWED_MIME_TYPES = {
        "application/pdf",
        "text/plain",
    }

    async def ingest_attachment(
        self,
        *,
        db: AsyncSession,
        user_id: str,
        attachment_id: str,
    ) -> Document:
        result = await db.execute(
            select(Attachment).where(
                Attachment.id == attachment_id,
                Attachment.user_id == user_id,
            )
        )
        attachment = result.scalar_one_or_none()

        if attachment is None:
            raise ValueError("Attachment not found.")

        if attachment.mime_type not in self.ALLOWED_MIME_TYPES:
            raise ValueError(
                "Only PDF and TXT files can currently be indexed for RAG."
            )

        existing_result = await db.execute(
            select(Document).where(
                Document.attachment_id == attachment.id,
                Document.user_id == user_id,
            )
        )
        existing = existing_result.scalar_one_or_none()

        if existing is not None:
            if existing.status == "ready":
                return existing

            if existing.status == "processing":
                raise ValueError(
                    "This document is already being processed."
                )

            # Explicit retry behavior: remove old chunks and reset the
            # failed document before starting a new ingestion attempt.
            await db.execute(
                delete(DocumentChunk).where(
                    DocumentChunk.document_id == existing.id,
                    DocumentChunk.user_id == user_id,
                )
            )

            existing.status = "processing"
            existing.error_message = None
            existing.extracted_text = None
            document = existing
        else:
            document = Document(
                user_id=user_id,
                attachment_id=attachment.id,
                name=attachment.original_name,
                mime_type=attachment.mime_type,
                size_bytes=attachment.size_bytes,
                status="processing",
            )
            db.add(document)

        try:
            await db.commit()
            await db.refresh(document)

            try:
                file_path = resolve_existing_storage_path(
                    settings.upload_dir,
                    user_id,
                    attachment.stored_name,
                    attachment.storage_path,
                )
            except (UnsafeStoragePathError, AttributeError) as exc:
                raise DocumentExtractionError(
                    "The attachment storage path is invalid."
                ) from exc

            if not file_path.is_file():
                raise DocumentExtractionError(
                    "The attachment file is missing from storage."
                )

            data = await asyncio.to_thread(file_path.read_bytes)

            if not data:
                raise DocumentExtractionError(
                    "The attachment file is empty."
                )

            if len(data) != attachment.size_bytes:
                raise DocumentExtractionError(
                    "The attachment size does not match its stored record."
                )

            extracted_text = await document_extraction_service.extract_text(
                data=data,
                mime_type=attachment.mime_type,
            )

            chunks = chunking_service.chunk_text(extracted_text)

            if not chunks:
                raise DocumentExtractionError(
                    "No usable text was produced from this document."
                )

            embeddings = await embedding_service.embed_documents(chunks)

            if len(embeddings) != len(chunks):
                raise RuntimeError(
                    "Embedding count does not match document chunk count."
                )

            document.extracted_text = extracted_text
            document.status = "ready"
            document.error_message = None

            for chunk_index, (content, embedding) in enumerate(
                zip(chunks, embeddings, strict=True)
            ):
                if not embedding:
                    raise RuntimeError(
                        f"Embedding for chunk {chunk_index} is empty."
                    )

                db.add(
                    DocumentChunk(
                        document_id=document.id,
                        user_id=user_id,
                        chunk_index=chunk_index,
                        content=content,
                        character_count=len(content),
                        embedding=embedding,
                        embedding_model=embedding_service.model,
                    )
                )

            # Persist the ready state and all chunks atomically.
            await db.commit()

            return await self.get_owned_document(
                db=db,
                user_id=user_id,
                document_id=document.id,
                include_chunks=True,
            )

        except Exception as exc:
            try:
                await db.rollback()
            except Exception:
                logger.exception(
                    "Rollback failed while ingesting document %s",
                    getattr(document, "id", None),
                )

            document_id = getattr(document, "id", None)

            if document_id:
                try:
                    failure_result = await db.execute(
                        select(Document).where(
                            Document.id == document_id,
                            Document.user_id == user_id,
                        )
                    )
                    persisted_document = failure_result.scalar_one_or_none()

                    if persisted_document is not None:
                        persisted_document.status = "failed"
                        persisted_document.error_message = (
                            f"Document processing failed: {type(exc).__name__}"
                        )
                        await db.commit()

                except Exception:
                    await db.rollback()
                    logger.exception(
                        "Could not persist ingestion failure for document %s",
                        document_id,
                    )

            raise

    async def get_documents(
        self,
        *,
        db: AsyncSession,
        user_id: str,
    ) -> list[Document]:
        result = await db.execute(
            select(Document)
            .where(Document.user_id == user_id)
            .order_by(Document.created_at.desc())
        )
        return list(result.scalars().all())

    async def get_owned_document(
        self,
        *,
        db: AsyncSession,
        user_id: str,
        document_id: str,
        include_chunks: bool = False,
    ) -> Document:
        statement = select(Document).where(
            Document.id == document_id,
            Document.user_id == user_id,
        )

        if include_chunks:
            statement = statement.options(
                selectinload(Document.chunks)
            )

        result = await db.execute(statement)
        document = result.scalar_one_or_none()

        if document is None:
            raise ValueError("Document not found.")

        return document

    async def delete_document(
        self,
        *,
        db: AsyncSession,
        user_id: str,
        document_id: str,
    ) -> None:
        try:
            document = await self.get_owned_document(
                db=db,
                user_id=user_id,
                document_id=document_id,
            )

            await db.execute(
                delete(DocumentChunk).where(
                    DocumentChunk.document_id == document.id,
                    DocumentChunk.user_id == user_id,
                )
            )

            await db.delete(document)
            await db.commit()

        except Exception:
            await db.rollback()
            raise


document_service = DocumentService()
