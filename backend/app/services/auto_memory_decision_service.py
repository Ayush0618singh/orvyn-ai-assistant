import re

from sqlalchemy.ext.asyncio import (
    AsyncSession,
)

from app.models.user import (
    User,
)
from app.schemas.auto_memory_decision import (
    AutoMemoryDecision,
    SimilarMemoryMatch,
)
from app.services.auto_memory_extractor_service import (
    auto_memory_extractor_service,
)
from app.services.memory_relationship_service import (
    memory_relationship_service,
)
from app.services.memory_service import (
    memory_service,
)


class AutoMemoryDecisionService:
    HIGH_DUPLICATE_THRESHOLD = 0.92

    RELATED_MEMORY_THRESHOLD = 0.65

    RELATIONSHIP_CONFIDENCE_THRESHOLD = (
        0.70
    )

    @staticmethod
    def _normalize_text(
        text: str,
    ) -> str:
        normalized = (
            text.strip().lower()
        )

        normalized = re.sub(
            r"[^\w\s]",
            " ",
            normalized,
        )

        normalized = re.sub(
            r"\s+",
            " ",
            normalized,
        )

        return normalized.strip()

    def _is_exact_duplicate(
        self,
        *,
        existing_content: str,
        candidate_content: str,
    ) -> bool:
        return (
            self._normalize_text(
                existing_content
            )
            == self._normalize_text(
                candidate_content
            )
        )

    @staticmethod
    def _build_match(
        *,
        memory,
        similarity: float,
    ) -> SimilarMemoryMatch:
        return SimilarMemoryMatch(
            id=memory.id,
            memory_type=(
                memory.memory_type
            ),
            content=memory.content,
            similarity=round(
                similarity,
                4,
            ),
        )

    async def decide(
        self,
        *,
        db: AsyncSession,
        user: User,
        user_message: str,
    ) -> AutoMemoryDecision:
        if not user.auto_memory_enabled:
            return AutoMemoryDecision(
                action="disabled",
                candidate=None,
                similar_memory=None,
                reason=(
                    "Automatic memory is disabled "
                    "for this user."
                ),
            )

        candidate = (
            await auto_memory_extractor_service
            .extract_candidate(
                user_message
            )
        )

        if not candidate.should_remember:
            return AutoMemoryDecision(
                action="ignored",
                candidate=candidate,
                similar_memory=None,
                reason=(
                    candidate.reason
                    or (
                        "The message was not suitable "
                        "for long-term memory."
                    )
                ),
            )

        if (
            not candidate.content
            or not candidate.memory_type
        ):
            return AutoMemoryDecision(
                action="ignored",
                candidate=candidate,
                similar_memory=None,
                reason=(
                    "The extracted memory candidate "
                    "was incomplete."
                ),
            )

        (
            similar_memory,
            similarity,
        ) = (
            await memory_service
            .find_similar_memory(
                db=db,
                user_id=user.id,
                content=candidate.content,
                memory_type=(
                    candidate.memory_type
                ),
                min_similarity=(
                    self.RELATED_MEMORY_THRESHOLD
                ),
            )
        )

        if similar_memory is None:
            return AutoMemoryDecision(
                action="save",
                candidate=candidate,
                similar_memory=None,
                reason=(
                    "No sufficiently related active "
                    "memory was found."
                ),
            )

        match = self._build_match(
            memory=similar_memory,
            similarity=similarity,
        )

        #
        # Deterministic exact duplicate detection.
        #
        if self._is_exact_duplicate(
            existing_content=(
                similar_memory.content
            ),
            candidate_content=(
                candidate.content
            ),
        ):
            return AutoMemoryDecision(
                action="duplicate",
                candidate=candidate,
                similar_memory=match,
                reason=(
                    "The same normalized memory "
                    "already exists."
                ),
            )

        #
        # Extremely high semantic similarity can
        # safely be treated as a duplicate.
        #
        if (
            similarity
            >= self.HIGH_DUPLICATE_THRESHOLD
        ):
            return AutoMemoryDecision(
                action="duplicate",
                candidate=candidate,
                similar_memory=match,
                reason=(
                    "A nearly identical semantic "
                    "memory already exists."
                ),
            )

        #
        # Related but non-identical memories need
        # semantic relationship resolution.
        #
        try:
            relationship = (
                await memory_relationship_service
                .resolve(
                    existing_memory=(
                        similar_memory.content
                    ),
                    new_candidate=(
                        candidate.content
                    ),
                )
            )

        except Exception:
            return AutoMemoryDecision(
                action="conflict",
                candidate=candidate,
                similar_memory=match,
                reason=(
                    "A related memory exists, but "
                    "its relationship could not be "
                    "resolved safely. Automatic "
                    "saving was blocked."
                ),
            )

        if (
            relationship.confidence
            < self.RELATIONSHIP_CONFIDENCE_THRESHOLD
        ):
            return AutoMemoryDecision(
                action="conflict",
                candidate=candidate,
                similar_memory=match,
                reason=(
                    "The relationship between the "
                    "existing and new memory was "
                    "uncertain. Automatic saving "
                    "was blocked."
                ),
            )

        if (
            relationship.relationship
            == "duplicate"
        ):
            return AutoMemoryDecision(
                action="duplicate",
                candidate=candidate,
                similar_memory=match,
                reason=(
                    "The relationship resolver "
                    "classified the candidate as "
                    "a duplicate."
                ),
            )

        if (
            relationship.relationship
            in {
                "replacement",
                "conflict",
            }
        ):
            return AutoMemoryDecision(
                action="conflict",
                candidate=candidate,
                similar_memory=match,
                reason=(
                    "The new memory may replace or "
                    "conflict with an existing "
                    "memory. Automatic overwrite "
                    "was blocked."
                ),
            )

        if (
            relationship.relationship
            in {
                "complementary",
                "unrelated",
            }
        ):
            return AutoMemoryDecision(
                action="save",
                candidate=candidate,
                similar_memory=match,
                reason=(
                    "The candidate adds distinct "
                    "long-term information and can "
                    "be stored separately."
                ),
            )

        return AutoMemoryDecision(
            action="conflict",
            candidate=candidate,
            similar_memory=match,
            reason=(
                "The memory relationship could "
                "not be handled safely."
            ),
        )


auto_memory_decision_service = (
    AutoMemoryDecisionService()
)