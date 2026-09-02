from dataclasses import dataclass

import numpy as np
from sqlalchemy import select
from sqlalchemy.ext.asyncio import (
    AsyncSession,
)

from app.core.config import settings
from app.models.attachment import (
    Attachment,
)
from app.models.document import (
    Document,
)
from app.models.document_chunk import (
    DocumentChunk,
)
from app.services.embedding_service import (
    embedding_service,
)


@dataclass(slots=True)
class RetrievedChunk:
    chunk_id: str
    document_id: str
    document_name: str
    chunk_index: int
    content: str
    similarity: float


class RAGService:

    async def get_conversation_document_ids(
        self,
        *,
        db: AsyncSession,
        user_id: str,
        conversation_id: str,
    ) -> list[str]:
        statement = (
            select(
                Document.id
            )
            .join(
                Attachment,
                Document.attachment_id
                == Attachment.id,
            )
            .where(
                Document.user_id
                == user_id,
                Document.status
                == "ready",
                Attachment.user_id
                == user_id,
                Attachment.conversation_id
                == conversation_id,
            )
            .order_by(
                Document.created_at.asc()
            )
        )

        result = await db.execute(
            statement
        )

        return list(
            result.scalars().all()
        )


    async def validate_document_ids(
        self,
        *,
        db: AsyncSession,
        user_id: str,
        document_ids: list[str],
    ) -> list[str]:
        if not document_ids:
            return []

        statement = (
            select(
                Document.id
            )
            .where(
                Document.user_id
                == user_id,
                Document.status
                == "ready",
                Document.id.in_(
                    document_ids
                ),
            )
        )

        result = await db.execute(
            statement
        )

        found_ids = list(
            result.scalars().all()
        )

        found_id_set = set(
            found_ids
        )

        missing_ids = [
            document_id
            for document_id
            in document_ids
            if document_id
            not in found_id_set
        ]

        if missing_ids:
            raise ValueError(
                "One or more selected documents "
                "were not found or are not ready."
            )

        return found_ids


    async def resolve_document_ids(
        self,
        *,
        db: AsyncSession,
        user_id: str,
        conversation_id: str,
        requested_document_ids:
            list[str]
            | None = None,
    ) -> list[str]:
        conversation_document_ids = (
            await self
            .get_conversation_document_ids(
                db=db,
                user_id=user_id,
                conversation_id=(
                    conversation_id
                ),
            )
        )

        requested_ids = (
            await self
            .validate_document_ids(
                db=db,
                user_id=user_id,
                document_ids=(
                    requested_document_ids
                    or []
                ),
            )
        )

        combined_ids: list[str] = []

        seen_ids: set[str] = set()

        for document_id in (
            conversation_document_ids
            + requested_ids
        ):
            if (
                document_id
                in seen_ids
            ):
                continue

            seen_ids.add(
                document_id
            )

            combined_ids.append(
                document_id
            )

        return combined_ids


    async def retrieve(
        self,
        *,
        db: AsyncSession,
        user_id: str,
        query: str,
        document_ids:
            list[str]
            | None = None,
    ) -> list[RetrievedChunk]:

        cleaned_query = (
            query.strip()
        )

        if not cleaned_query:
            return []

        query_embedding = (
            await embedding_service
            .embed_query(
                cleaned_query
            )
        )

        statement = (
            select(
                DocumentChunk,
                Document.name,
            )
            .join(
                Document,
                Document.id
                == DocumentChunk.document_id,
            )
            .where(
                DocumentChunk.user_id
                == user_id,
                Document.user_id
                == user_id,
                Document.status
                == "ready",
            )
        )

        if document_ids:
            statement = (
                statement.where(
                    DocumentChunk.document_id.in_(
                        document_ids
                    )
                )
            )

        result = await db.execute(
            statement
        )

        rows = result.all()

        if not rows:
            return []

        query_vector = np.asarray(
            query_embedding,
            dtype=np.float32,
        )

        query_norm = np.linalg.norm(
            query_vector
        )

        if query_norm == 0:
            return []

        retrieved: list[
            RetrievedChunk
        ] = []

        for (
            chunk,
            document_name,
        ) in rows:

            if not chunk.embedding:
                continue

            chunk_vector = np.asarray(
                chunk.embedding,
                dtype=np.float32,
            )

            if (
                chunk_vector.shape
                != query_vector.shape
            ):
                continue

            chunk_norm = np.linalg.norm(
                chunk_vector
            )

            if chunk_norm == 0:
                continue

            similarity = float(
                np.dot(
                    query_vector,
                    chunk_vector,
                )
                /
                (
                    query_norm
                    * chunk_norm
                )
            )

            if (
                similarity
                < settings.rag_min_similarity
            ):
                continue

            retrieved.append(
                RetrievedChunk(
                    chunk_id=(
                        chunk.id
                    ),
                    document_id=(
                        chunk.document_id
                    ),
                    document_name=(
                        document_name
                    ),
                    chunk_index=(
                        chunk.chunk_index
                    ),
                    content=(
                        chunk.content
                    ),
                    similarity=(
                        similarity
                    ),
                )
            )

        retrieved.sort(
            key=lambda item:
                item.similarity,
            reverse=True,
        )

        return retrieved[
            : settings.rag_top_k
        ]


    def build_context(
        self,
        chunks:
            list[RetrievedChunk],
    ) -> str:

        if not chunks:
            return ""

        sections: list[str] = []

        for (
            index,
            chunk,
        ) in enumerate(
            chunks,
            start=1,
        ):
            sections.append(
                (
                    f"[Source {index}]\n"
                    f"Document: "
                    f"{chunk.document_name}\n"
                    f"Chunk: "
                    f"{chunk.chunk_index}\n"
                    f"Content:\n"
                    f"{chunk.content}"
                )
            )

        return "\n\n".join(
            sections
        )


rag_service = RAGService()