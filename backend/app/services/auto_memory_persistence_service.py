from sqlalchemy.ext.asyncio import (
    AsyncSession,
)

from app.models.user import (
    User,
)
from app.schemas.auto_memory_decision import (
    AutoMemoryPersistenceResult,
    SavedMemoryResult,
)
from app.schemas.memory import (
    MemoryCreate,
)
from app.services.auto_memory_decision_service import (
    auto_memory_decision_service,
)
from app.services.memory_service import (
    memory_service,
)


class AutoMemoryPersistenceService:
    async def process(
        self,
        *,
        db: AsyncSession,
        user: User,
        user_message: str,
        source_message_id: (
            str | None
        ) = None,
    ) -> AutoMemoryPersistenceResult:
        decision = (
            await auto_memory_decision_service
            .decide(
                db=db,
                user=user,
                user_message=user_message,
            )
        )

        if decision.action == "disabled":
            return (
                AutoMemoryPersistenceResult(
                    action="disabled",
                    candidate=(
                        decision.candidate
                    ),
                    similar_memory=(
                        decision.similar_memory
                    ),
                    saved_memory=None,
                    reason=decision.reason,
                )
            )

        if decision.action == "ignored":
            return (
                AutoMemoryPersistenceResult(
                    action="ignored",
                    candidate=(
                        decision.candidate
                    ),
                    similar_memory=(
                        decision.similar_memory
                    ),
                    saved_memory=None,
                    reason=decision.reason,
                )
            )

        if decision.action == "duplicate":
            return (
                AutoMemoryPersistenceResult(
                    action="duplicate",
                    candidate=(
                        decision.candidate
                    ),
                    similar_memory=(
                        decision.similar_memory
                    ),
                    saved_memory=None,
                    reason=decision.reason,
                )
            )

        if decision.action == "conflict":
            return (
                AutoMemoryPersistenceResult(
                    action="conflict",
                    candidate=(
                        decision.candidate
                    ),
                    similar_memory=(
                        decision.similar_memory
                    ),
                    saved_memory=None,
                    reason=decision.reason,
                )
            )

        candidate = decision.candidate

        if (
            candidate is None
            or not candidate.content
            or not candidate.memory_type
        ):
            return (
                AutoMemoryPersistenceResult(
                    action="ignored",
                    candidate=candidate,
                    similar_memory=None,
                    saved_memory=None,
                    reason=(
                        "The final memory candidate "
                        "was incomplete."
                    ),
                )
            )

        memory = (
            await memory_service
            .create_memory(
                db=db,
                user_id=user.id,
                payload=MemoryCreate(
                    memory_type=(
                        candidate.memory_type
                    ),
                    content=(
                        candidate.content
                    ),
                    importance=(
                        candidate.importance
                    ),
                    source_message_id=(
                        source_message_id
                    ),
                ),
            )
        )

        return AutoMemoryPersistenceResult(
            action="saved",
            candidate=candidate,
            similar_memory=None,
            saved_memory=(
                SavedMemoryResult(
                    id=memory.id,
                    memory_type=(
                        memory.memory_type
                    ),
                    content=memory.content,
                    importance=(
                        memory.importance
                    ),
                )
            ),
            reason=(
                "The memory was safely saved."
            ),
        )


auto_memory_persistence_service = (
    AutoMemoryPersistenceService()
)