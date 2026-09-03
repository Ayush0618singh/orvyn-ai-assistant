from app.schemas.memory_candidate import (
    MemoryCandidate,
)
from app.services.memory_policy_service import (
    memory_policy_service,
)
from app.services.memory_safety_service import (
    memory_safety_service,
)


class AutoMemoryService:
    """
    Safe first-stage automatic memory candidate evaluator.

    At this stage it does NOT write anything to the database.

    Pipeline:
        user message
        -> safety check
        -> deterministic usefulness policy
        -> candidate result
    """

    def evaluate_message(
        self,
        user_message: str,
    ) -> MemoryCandidate:
        safety_result = (
            memory_safety_service.check(
                user_message
            )
        )

        if not safety_result.allowed:
            return MemoryCandidate(
                should_remember=False,
                confidence=1.0,
                reason=(
                    "Automatic memory blocked: "
                    f"{safety_result.reason}"
                ),
            )

        candidate = (
            memory_policy_service
            .evaluate(
                user_message
            )
        )

        return candidate


auto_memory_service = (
    AutoMemoryService()
)