import asyncio
from pathlib import Path

from sqlalchemy import (
    delete,
    select,
)
from sqlalchemy.ext.asyncio import (
    AsyncSession,
)
from sqlalchemy.orm import (
    selectinload,
)

from app.models.attachment import (
    Attachment,
)
from app.models.document import (
    Document,
)
from app.models.document_chunk import (
    DocumentChunk,
)
from app.services.chunking_service import (
    chunking_service,
)
from app.services.document_extraction_service import (
    DocumentExtractionError,
    document_extraction_service,
)
from app.services.embedding_service import (
    embedding_service,
)


class DocumentService:

    async def ingest_attachment(
        self,
        *,
        db: AsyncSession,
        user_id: str,
        attachment_id: str,
    ) -> Document:

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

        if attachment is None:
            raise ValueError(
                "Attachment not found."
            )

        if attachment.mime_type not in {
            "application/pdf",
            "text/plain",
        }:
            raise ValueError(
                (
                    "Only PDF and TXT files can "
                    "currently be indexed for RAG."
                )
            )

        existing_result = (
            await db.execute(
                select(
                    Document
                ).where(
                    Document.attachment_id
                    == attachment.id
                )
            )
        )

        existing = (
            existing_result
            .scalar_one_or_none()
        )

        if existing is not None:
            return existing

        document = Document(
            user_id=user_id,
            attachment_id=(
                attachment.id
            ),
            name=(
                attachment.original_name
            ),
            mime_type=(
                attachment.mime_type
            ),
            size_bytes=(
                attachment.size_bytes
            ),
            status="processing",
        )

        db.add(
            document
        )

        await db.commit()
        await db.refresh(
            document
        )

        try:
            data = (
                await asyncio.to_thread(
                    Path(
                        attachment.storage_path
                    ).read_bytes
                )
            )

            extracted_text = (
                await document_extraction_service
                .extract_text(
                    data=data,
                    mime_type=(
                        attachment.mime_type
                    ),
                )
            )

            chunks = (
                chunking_service
                .chunk_text(
                    extracted_text
                )
            )

            if not chunks:
                raise (
                    DocumentExtractionError(
                        (
                            "No usable text was produced "
                            "from this document."
                        )
                    )
                )

            embeddings = (
                await embedding_service
                .embed_documents(
                    chunks
                )
            )

            document.extracted_text = (
                extracted_text
            )

            document.status = "ready"
            document.error_message = None

            for (
                chunk_index,
                (
                    chunk_content,
                    embedding,
                ),
            ) in enumerate(
                zip(
                    chunks,
                    embeddings,
                    strict=True,
                )
            ):
                db.add(
                    DocumentChunk(
                        document_id=(
                            document.id
                        ),
                        user_id=user_id,
                        chunk_index=(
                            chunk_index
                        ),
                        content=(
                            chunk_content
                        ),
                        character_count=len(
                            chunk_content
                        ),
                        embedding=(
                            embedding
                        ),
                        embedding_model=(
                            embedding_service.model
                        ),
                    )
                )

            await db.commit()

            return await self.get_owned_document(
                db=db,
                user_id=user_id,
                document_id=(
                    document.id
                ),
                include_chunks=True,
            )

        except Exception as exc:

            document.status = "failed"

            document.error_message = (
                str(exc)[:2000]
            )

            await db.commit()

            raise


    async def get_documents(
        self,
        *,
        db: AsyncSession,
        user_id: str,
    ) -> list[Document]:

        result = await db.execute(
            select(
                Document
            )
            .where(
                Document.user_id
                == user_id
            )
            .order_by(
                Document.created_at.desc()
            )
        )

        return list(
            result.scalars().all()
        )


    async def get_owned_document(
        self,
        *,
        db: AsyncSession,
        user_id: str,
        document_id: str,
        include_chunks:
            bool = False,
    ) -> Document:

        statement = (
            select(
                Document
            ).where(
                Document.id
                == document_id,
                Document.user_id
                == user_id,
            )
        )

        if include_chunks:
            statement = (
                statement.options(
                    selectinload(
                        Document.chunks
                    )
                )
            )

        result = await db.execute(
            statement
        )

        document = (
            result.scalar_one_or_none()
        )

        if document is None:
            raise ValueError(
                "Document not found."
            )

        return document


    async def delete_document(
        self,
        *,
        db: AsyncSession,
        user_id: str,
        document_id: str,
    ) -> None:

        document = (
            await self
            .get_owned_document(
                db=db,
                user_id=user_id,
                document_id=(
                    document_id
                ),
            )
        )

        await db.execute(
            delete(
                DocumentChunk
            ).where(
                DocumentChunk.document_id
                == document.id
            )
        )

        await db.delete(
            document
        )

        await db.commit()


document_service = (
    DocumentService()
)