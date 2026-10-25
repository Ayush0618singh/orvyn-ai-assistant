
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.attachment import Attachment
from app.models.document import Document
from app.models.document_chunk import DocumentChunk
from app.services.embedding_service import embedding_service


@dataclass(slots=True, frozen=True)
class RetrievedChunk:
    chunk_id: str
    document_id: str
    document_name: str
    chunk_index: int
    content: str
    similarity: float


class RAGService:
    """Retrieve relevant, user-owned document chunks for grounded answers."""

    async def get_conversation_document_ids(
        self,
        *,
        db: AsyncSession,
        user_id: str,
        conversation_id: str,
    ) -> list[str]:
        statement = (
            select(Document.id)
            .join(Attachment, Document.attachment_id == Attachment.id)
            .where(
                Document.user_id == user_id,
                Document.status == "ready",
                Attachment.user_id == user_id,
                Attachment.conversation_id == conversation_id,
            )
            .order_by(Document.created_at.asc())
        )

        result = await db.execute(statement)
        return list(result.scalars().all())

    async def validate_document_ids(
        self,
        *,
        db: AsyncSession,
        user_id: str,
        document_ids: list[str],
    ) -> list[str]:
        if not document_ids:
            return []

        unique_ids = list(dict.fromkeys(document_ids))

        statement = select(Document.id).where(
            Document.user_id == user_id,
            Document.status == "ready",
            Document.id.in_(unique_ids),
        )

        result = await db.execute(statement)
        found_ids = set(result.scalars().all())

        if any(document_id not in found_ids for document_id in unique_ids):
            raise ValueError(
                "One or more selected documents were not found "
                "or are not ready."
            )

        return unique_ids

    async def resolve_document_ids(
        self,
        *,
        db: AsyncSession,
        user_id: str,
        conversation_id: str,
        requested_document_ids: list[str] | None = None,
    ) -> list[str]:
        conversation_ids = await self.get_conversation_document_ids(
            db=db,
            user_id=user_id,
            conversation_id=conversation_id,
        )

        requested_ids = await self.validate_document_ids(
            db=db,
            user_id=user_id,
            document_ids=requested_document_ids or [],
        )

        return list(dict.fromkeys(conversation_ids + requested_ids))

    async def retrieve(
        self,
        *,
        db: AsyncSession,
        user_id: str,
        query: str,
        document_ids: list[str] | None = None,
    ) -> list[RetrievedChunk]:
        if not isinstance(query, str):
            return []

        cleaned_query = query.strip()

        if not cleaned_query:
            return []

        validated_ids: list[str] | None = None

        if document_ids:
            validated_ids = await self.validate_document_ids(
                db=db,
                user_id=user_id,
                document_ids=document_ids,
            )

            if not validated_ids:
                return []

        query_embedding = await embedding_service.embed_query(cleaned_query)

        if query_embedding is None:
            return []

        try:
            query_vector = np.asarray(query_embedding, dtype=np.float32)
        except (TypeError, ValueError, OverflowError):
            return []

        if query_vector.ndim != 1 or query_vector.size == 0:
            return []

        if not np.all(np.isfinite(query_vector)):
            return []

        query_norm = float(np.linalg.norm(query_vector))

        if not np.isfinite(query_norm) or query_norm == 0:
            return []

        statement = (
            select(DocumentChunk, Document.name)
            .join(Document, Document.id == DocumentChunk.document_id)
            .where(
                DocumentChunk.user_id == user_id,
                Document.user_id == user_id,
                Document.status == "ready",
            )
        )

        if validated_ids is not None:
            statement = statement.where(
                DocumentChunk.document_id.in_(validated_ids)
            )

        result = await db.execute(statement)
        rows = result.all()

        retrieved: list[RetrievedChunk] = []

        for chunk, document_name in rows:
            if chunk.embedding is None:
                continue

            try:
                chunk_vector = np.asarray(
                    chunk.embedding,
                    dtype=np.float32,
                )
            except (TypeError, ValueError, OverflowError):
                continue

            if chunk_vector.ndim != 1:
                continue

            if chunk_vector.shape != query_vector.shape:
                continue

            if not np.all(np.isfinite(chunk_vector)):
                continue

            chunk_norm = float(np.linalg.norm(chunk_vector))

            if not np.isfinite(chunk_norm) or chunk_norm == 0:
                continue

            similarity = float(
                np.dot(query_vector, chunk_vector)
                / (query_norm * chunk_norm)
            )

            if not np.isfinite(similarity):
                continue

            if similarity < settings.rag_min_similarity:
                continue

            retrieved.append(
                RetrievedChunk(
                    chunk_id=chunk.id,
                    document_id=chunk.document_id,
                    document_name=document_name,
                    chunk_index=chunk.chunk_index,
                    content=chunk.content,
                    similarity=similarity,
                )
            )

        retrieved.sort(
            key=lambda item: item.similarity,
            reverse=True,
        )

        top_k = max(0, int(settings.rag_top_k))
        return retrieved[:top_k]

    def build_context(
        self,
        chunks: list[RetrievedChunk],
        *,
        max_chars: int = 24000,
    ) -> str:
        """Build bounded context with stable source identifiers."""
        if not chunks or max_chars <= 0:
            return ""

        sections: list[str] = []
        used_chars = 0

        for index, chunk in enumerate(chunks, start=1):
            section = (
                f"[Source {index}]\n"
                f"Document: {chunk.document_name}\n"
                f"Document ID: {chunk.document_id}\n"
                f"Chunk ID: {chunk.chunk_id}\n"
                f"Chunk: {chunk.chunk_index}\n"
                f"Similarity: {chunk.similarity:.4f}\n"
                f"Content:\n{chunk.content}"
            )

            separator = "\n\n" if sections else ""
            remaining = max_chars - used_chars - len(separator)

            if remaining <= 0:
                break

            if len(section) > remaining:
                if not sections:
                    sections.append(section[:remaining])
                break

            sections.append(section)
            used_chars += len(separator) + len(section)

        return "\n\n".join(sections)


rag_service = RAGService()
