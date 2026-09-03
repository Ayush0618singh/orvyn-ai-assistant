from datetime import (
    datetime,
    timezone,
)

import numpy as np

from fastapi import (
    HTTPException,
    status,
)
from sqlalchemy import (
    select,
)
from sqlalchemy.ext.asyncio import (
    AsyncSession,
)

from app.core.config import settings
from app.models.memory import (
    Memory,
)
from app.models.message import (
    Message,
)
from app.schemas.memory import (
    MemoryCreate,
    MemorySearchRequest,
    MemoryUpdate,
)
from app.services.embedding_service import (
    embedding_service,
)


class MemoryService:
    @staticmethod
    def _cosine_similarity(
        left: list[float],
        right: list[float],
    ) -> float:
        left_array = np.asarray(
            left,
            dtype=np.float32,
        )

        right_array = np.asarray(
            right,
            dtype=np.float32,
        )

        if (
            left_array.size == 0
            or right_array.size == 0
        ):
            return 0.0

        left_norm = np.linalg.norm(
            left_array
        )

        right_norm = np.linalg.norm(
            right_array
        )

        if (
            left_norm == 0
            or right_norm == 0
        ):
            return 0.0

        return float(
            np.dot(
                left_array,
                right_array,
            )
            / (
                left_norm
                * right_norm
            )
        )

    async def _validate_source_message(
        self,
        *,
        db: AsyncSession,
        user_id: str,
        source_message_id: (
            str | None
        ),
    ) -> None:
        if not source_message_id:
            return

        statement = (
            select(
                Message.id
            )
            .join(
                Message.conversation
            )
            .where(
                Message.id
                == source_message_id,
                Message.conversation
                .has(
                    user_id=user_id
                ),
            )
        )

        result = await db.execute(
            statement
        )

        if (
            result.scalar_one_or_none()
            is None
        ):
            raise HTTPException(
                status_code=(
                    status.HTTP_404_NOT_FOUND
                ),
                detail=(
                    "Source message not found."
                ),
            )

    async def create_memory(
        self,
        *,
        db: AsyncSession,
        user_id: str,
        payload: MemoryCreate,
    ) -> Memory:
        await self._validate_source_message(
            db=db,
            user_id=user_id,
            source_message_id=(
                payload.source_message_id
            ),
        )

        embeddings = (
            await embedding_service
            .embed_documents(
                [
                    payload.content
                ]
            )
        )

        if (
            not embeddings
            or not embeddings[0]
        ):
            raise RuntimeError(
                "Unable to create memory embedding."
            )

        memory = Memory(
            user_id=user_id,
            source_message_id=(
                payload.source_message_id
            ),
            memory_type=(
                payload.memory_type
            ),
            content=(
                payload.content
            ),
            importance=(
                payload.importance
            ),
            embedding=(
                embeddings[0]
            ),
            embedding_model=(
                settings.embedding_model
            ),
            is_active=True,
        )

        db.add(
            memory
        )

        await db.commit()

        await db.refresh(
            memory
        )

        return memory

    async def list_memories(
        self,
        *,
        db: AsyncSession,
        user_id: str,
        memory_type: (
            str | None
        ) = None,
        active_only: bool = True,
    ) -> list[Memory]:
        statement = (
            select(
                Memory
            )
            .where(
                Memory.user_id
                == user_id
            )
        )

        if memory_type:
            statement = (
                statement.where(
                    Memory.memory_type
                    == memory_type
                )
            )

        if active_only:
            statement = (
                statement.where(
                    Memory.is_active
                    .is_(True)
                )
            )

        statement = (
            statement.order_by(
                Memory.updated_at.desc()
            )
        )

        result = await db.execute(
            statement
        )

        return list(
            result.scalars().all()
        )

    async def get_memory(
        self,
        *,
        db: AsyncSession,
        user_id: str,
        memory_id: str,
    ) -> Memory:
        result = await db.execute(
            select(
                Memory
            ).where(
                Memory.id
                == memory_id,
                Memory.user_id
                == user_id,
            )
        )

        memory = (
            result.scalar_one_or_none()
        )

        if not memory:
            raise HTTPException(
                status_code=(
                    status.HTTP_404_NOT_FOUND
                ),
                detail=(
                    "Memory not found."
                ),
            )

        return memory

    async def update_memory(
        self,
        *,
        db: AsyncSession,
        user_id: str,
        memory_id: str,
        payload: MemoryUpdate,
    ) -> Memory:
        memory = (
            await self.get_memory(
                db=db,
                user_id=user_id,
                memory_id=memory_id,
            )
        )

        content_changed = False

        if payload.content is not None:
            if (
                payload.content
                != memory.content
            ):
                memory.content = (
                    payload.content
                )

                content_changed = True

        if (
            payload.memory_type
            is not None
        ):
            memory.memory_type = (
                payload.memory_type
            )

        if (
            payload.importance
            is not None
        ):
            memory.importance = (
                payload.importance
            )

        if (
            payload.is_active
            is not None
        ):
            memory.is_active = (
                payload.is_active
            )

        if content_changed:
            embeddings = (
                await embedding_service
                .embed_documents(
                    [
                        memory.content
                    ]
                )
            )

            if (
                not embeddings
                or not embeddings[0]
            ):
                raise RuntimeError(
                    "Unable to update memory embedding."
                )

            memory.embedding = (
                embeddings[0]
            )

            memory.embedding_model = (
                settings.embedding_model
            )

        memory.updated_at = (
            datetime.now(
                timezone.utc
            )
        )

        await db.commit()

        await db.refresh(
            memory
        )

        return memory

    async def delete_memory(
        self,
        *,
        db: AsyncSession,
        user_id: str,
        memory_id: str,
    ) -> None:
        memory = (
            await self.get_memory(
                db=db,
                user_id=user_id,
                memory_id=memory_id,
            )
        )

        await db.delete(
            memory
        )

        await db.commit()

    async def find_similar_memory(
        self,
        *,
        db: AsyncSession,
        user_id: str,
        content: str,
        memory_type: (
            str | None
        ) = None,
        min_similarity: float = 0.0,
    ) -> tuple[
        Memory | None,
        float,
    ]:
        """
        Find the single most semantically similar active
        memory belonging to the current user.

        This method does not modify last_used_at because it
        is used for duplicate/conflict detection rather than
        conversational memory retrieval.
        """

        query_embedding = (
            await embedding_service
            .embed_query(
                content
            )
        )

        statement = (
            select(
                Memory
            )
            .where(
                Memory.user_id
                == user_id,
                Memory.is_active
                .is_(True),
            )
        )

        if memory_type:
            statement = (
                statement.where(
                    Memory.memory_type
                    == memory_type
                )
            )

        result = await db.execute(
            statement
        )

        memories = list(
            result.scalars().all()
        )

        best_memory: (
            Memory | None
        ) = None

        best_similarity = 0.0

        for memory in memories:
            if not memory.embedding:
                continue

            similarity = (
                self._cosine_similarity(
                    query_embedding,
                    memory.embedding,
                )
            )

            if (
                similarity
                > best_similarity
            ):
                best_memory = memory
                best_similarity = (
                    similarity
                )

        if (
            best_memory is None
            or best_similarity
            < min_similarity
        ):
            return (
                None,
                best_similarity,
            )

        return (
            best_memory,
            best_similarity,
        )

    async def search_memories(
        self,
        *,
        db: AsyncSession,
        user_id: str,
        payload: MemorySearchRequest,
    ) -> list[dict]:
        query_embedding = (
            await embedding_service
            .embed_query(
                payload.query
            )
        )

        statement = (
            select(
                Memory
            )
            .where(
                Memory.user_id
                == user_id,
                Memory.is_active
                .is_(True),
            )
        )

        if payload.memory_types:
            statement = (
                statement.where(
                    Memory.memory_type
                    .in_(
                        payload.memory_types
                    )
                )
            )

        result = await db.execute(
            statement
        )

        memories = list(
            result.scalars().all()
        )

        scored_memories: list[
            tuple[
                Memory,
                float,
            ]
        ] = []

        for memory in memories:
            if not memory.embedding:
                continue

            similarity = (
                self._cosine_similarity(
                    query_embedding,
                    memory.embedding,
                )
            )

            if (
                similarity
                < payload.min_similarity
            ):
                continue

            scored_memories.append(
                (
                    memory,
                    similarity,
                )
            )

        scored_memories.sort(
            key=lambda item: (
                item[1],
                item[0].importance,
            ),
            reverse=True,
        )

        selected = (
            scored_memories[
                :payload.limit
            ]
        )

        now = datetime.now(
            timezone.utc
        )

        response: list[
            dict
        ] = []

        for (
            memory,
            similarity,
        ) in selected:
            memory.last_used_at = now

            response.append(
                {
                    "id":
                        memory.id,

                    "memory_type":
                        memory.memory_type,

                    "content":
                        memory.content,

                    "importance":
                        memory.importance,

                    "similarity":
                        round(
                            similarity,
                            4,
                        ),
                }
            )

        if selected:
            await db.commit()

        return response


memory_service = MemoryService()