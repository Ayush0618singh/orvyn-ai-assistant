import re
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import (
    AsyncSession,
)

from app.schemas.memory import (
    MemoryCreate,
    MemorySearchRequest,
)
from app.services.memory_service import (
    memory_service,
)


@dataclass
class MemoryIntent:
    action: str

    content: str | None = None

    memory_type: str = "fact"

    importance: float = 0.7


class MemoryChatService:
    REMEMBER_PATTERNS = [
        r"^remember that\s+(.+)$",
        r"^remember\s+(.+)$",
        r"^please remember that\s+(.+)$",
        r"^please remember\s+(.+)$",
        r"^yaad rakhna ki\s+(.+)$",
        r"^yaad rakhna\s+(.+)$",
        r"^yaad rakh lo ki\s+(.+)$",
        r"^yaad rakh lo\s+(.+)$",
        r"^note that\s+(.+)$",
        r"^note kar lo ki\s+(.+)$",
        r"^note kar lo\s+(.+)$",
    ]

    FORGET_PATTERNS = [
        r"^forget that\s+(.+)$",
        r"^forget\s+(.+)$",
        r"^please forget that\s+(.+)$",
        r"^please forget\s+(.+)$",
        r"^bhool jao ki\s+(.+)$",
        r"^bhool jao\s+(.+)$",
        r"^yaad mat rakhna ki\s+(.+)$",
        r"^yaad mat rakhna\s+(.+)$",
    ]

    SHOW_MEMORY_PATTERNS = [
        r"^what do you remember about me\??$",
        r"^what do you remember\??$",
        r"^show my memories\??$",
        r"^show memories\??$",
        r"^mere bare me kya yaad hai\??$",
        r"^mujhe kya yaad rakha hai\??$",
    ]

    def detect_intent(
        self,
        message: str,
    ) -> MemoryIntent:
        cleaned = (
            message
            .strip()
        )

        lowered = (
            cleaned
            .lower()
        )

        for pattern in (
            self.REMEMBER_PATTERNS
        ):
            match = re.match(
                pattern,
                lowered,
                flags=re.IGNORECASE,
            )

            if match:
                content = (
                    cleaned[
                        match.start(1):
                        match.end(1)
                    ]
                    .strip()
                )

                return MemoryIntent(
                    action="remember",
                    content=content,
                    memory_type=(
                        self._infer_type(
                            content
                        )
                    ),
                    importance=(
                        self._infer_importance(
                            content
                        )
                    ),
                )

        for pattern in (
            self.FORGET_PATTERNS
        ):
            match = re.match(
                pattern,
                lowered,
                flags=re.IGNORECASE,
            )

            if match:
                content = (
                    cleaned[
                        match.start(1):
                        match.end(1)
                    ]
                    .strip()
                )

                return MemoryIntent(
                    action="forget",
                    content=content,
                )

        for pattern in (
            self.SHOW_MEMORY_PATTERNS
        ):
            if re.match(
                pattern,
                lowered,
                flags=re.IGNORECASE,
            ):
                return MemoryIntent(
                    action="show"
                )

        return MemoryIntent(
            action="none"
        )

    @staticmethod
    def _infer_type(
        content: str,
    ) -> str:
        lowered = (
            content.lower()
        )

        preference_words = {
            "prefer",
            "preferred",
            "like",
            "pasand",
        }

        instruction_words = {
            "call me",
            "address me",
            "always",
            "from now on",
            "hamesha",
        }

        note_words = {
            "remind",
            "call",
            "meeting",
            "todo",
            "task",
            "sunday",
            "monday",
            "tuesday",
            "wednesday",
            "thursday",
            "friday",
            "saturday",
        }

        if any(
            word in lowered
            for word
            in preference_words
        ):
            return "preference"

        if any(
            word in lowered
            for word
            in instruction_words
        ):
            return "instruction"

        if any(
            word in lowered
            for word
            in note_words
        ):
            return "note"

        return "fact"

    @staticmethod
    def _infer_importance(
        content: str,
    ) -> float:
        lowered = (
            content.lower()
        )

        high_importance_words = {
            "important",
            "always",
            "never",
            "must",
            "hamesha",
            "zaroor",
        }

        if any(
            word in lowered
            for word
            in high_importance_words
        ):
            return 0.9

        return 0.7

    async def find_duplicate(
        self,
        *,
        db: AsyncSession,
        user_id: str,
        content: str,
    ):
        results = (
            await memory_service
            .search_memories(
                db=db,
                user_id=user_id,
                payload=(
                    MemorySearchRequest(
                        query=content,
                        limit=3,
                        min_similarity=0.88,
                    )
                ),
            )
        )

        if not results:
            return None

        return results[0]

    async def remember(
        self,
        *,
        db: AsyncSession,
        user_id: str,
        content: str,
        memory_type: str,
        importance: float,
        source_message_id: (
            str | None
        ) = None,
    ):
        duplicate = (
            await self.find_duplicate(
                db=db,
                user_id=user_id,
                content=content,
            )
        )

        if duplicate:
            return {
                "created": False,
                "memory": duplicate,
            }

        memory = (
            await memory_service
            .create_memory(
                db=db,
                user_id=user_id,
                payload=(
                    MemoryCreate(
                        content=content,
                        memory_type=(
                            memory_type
                        ),
                        importance=(
                            importance
                        ),
                        source_message_id=(
                            source_message_id
                        ),
                    )
                ),
            )
        )

        return {
            "created": True,
            "memory": memory,
        }

    async def forget(
        self,
        *,
        db: AsyncSession,
        user_id: str,
        content: str,
    ) -> dict:
        matches = (
            await memory_service
            .search_memories(
                db=db,
                user_id=user_id,
                payload=(
                    MemorySearchRequest(
                        query=content,
                        limit=3,
                        min_similarity=0.55,
                    )
                ),
            )
        )

        if not matches:
            return {
                "deleted": False,
                "count": 0,
            }

        best_match = (
            matches[0]
        )

        await memory_service.delete_memory(
            db=db,
            user_id=user_id,
            memory_id=(
                best_match["id"]
            ),
        )

        return {
            "deleted": True,
            "count": 1,
            "memory": best_match,
        }

    async def get_relevant_memories(
        self,
        *,
        db: AsyncSession,
        user_id: str,
        query: str,
        limit: int = 5,
    ) -> list[dict]:
        if not query.strip():
            return []

        return (
            await memory_service
            .search_memories(
                db=db,
                user_id=user_id,
                payload=(
                    MemorySearchRequest(
                        query=query,
                        limit=limit,
                        min_similarity=0.30,
                    )
                ),
            )
        )

    @staticmethod
    def build_memory_context(
        memories: list[dict],
    ) -> str:
        if not memories:
            return ""

        lines = [
            "USER LONG-TERM MEMORY:",
        ]

        for index, memory in enumerate(
            memories,
            start=1,
        ):
            lines.append(
                (
                    f"[Memory {index}] "
                    f"Type: "
                    f"{memory['memory_type']}\n"
                    f"{memory['content']}"
                )
            )

        return "\n\n".join(
            lines
        )


memory_chat_service = (
    MemoryChatService()
)