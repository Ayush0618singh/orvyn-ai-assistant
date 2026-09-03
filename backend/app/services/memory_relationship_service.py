import json
import re
from typing import Any

from pydantic import (
    ValidationError,
)

from app.schemas.memory_relationship import (
    MemoryRelationshipResult,
)
from app.services.chat_service import (
    get_chat_service,
)


RELATIONSHIP_SYSTEM_PROMPT = """
You are ORVYN's long-term memory relationship resolver.

You will receive:

1. An EXISTING MEMORY.
2. A NEW MEMORY CANDIDATE.

Your only task is to determine the relationship between them.

Allowed relationships:

duplicate
- They communicate essentially the same durable information.

complementary
- They are related and can both be true.
- The new memory adds useful information without replacing the old memory.

replacement
- The new memory appears to be an updated version of the same user fact,
  preference, profile detail, or instruction.
- The new information should logically replace the old information.

conflict
- The two memories make incompatible claims and it is not sufficiently clear
  that the new one should replace the old one.

unrelated
- They are not meaningfully about the same persistent user information.

Examples:

Existing:
"I prefer Python for backend development."

New:
"I prefer Python for backend development."

Result:
duplicate


Existing:
"I prefer Python for backend development."

New:
"I prefer FastAPI when building Python APIs."

Result:
complementary


Existing:
"I prefer MongoDB for production databases."

New:
"I now prefer PostgreSQL for production databases."

Result:
replacement


Existing:
"My preferred frontend framework is React."

New:
"My preferred frontend framework is Vue."

Result:
conflict


Existing:
"I prefer concise explanations."

New:
"I prefer PostgreSQL for production databases."

Result:
unrelated


Do not assume that semantic similarity means contradiction.

Do not invent user information.

Return ONLY valid JSON in this exact structure:

{
  "relationship": "duplicate | complementary | replacement | conflict | unrelated",
  "confidence": 0.0,
  "reason": "short explanation"
}

Do not use markdown.
""".strip()


class MemoryRelationshipService:
    @staticmethod
    def _extract_json(
        text: str,
    ) -> dict[str, Any]:
        cleaned = text.strip()

        if cleaned.startswith("```"):
            cleaned = re.sub(
                r"^```(?:json)?\s*",
                "",
                cleaned,
                flags=re.IGNORECASE,
            )

            cleaned = re.sub(
                r"\s*```$",
                "",
                cleaned,
            )

        try:
            parsed = json.loads(
                cleaned
            )

            if not isinstance(
                parsed,
                dict,
            ):
                raise ValueError(
                    "Memory relationship result "
                    "must be a JSON object."
                )

            return parsed

        except json.JSONDecodeError:
            match = re.search(
                r"\{.*\}",
                cleaned,
                flags=re.DOTALL,
            )

            if not match:
                raise ValueError(
                    "Memory relationship model "
                    "did not return valid JSON."
                )

            try:
                parsed = json.loads(
                    match.group(0)
                )

            except json.JSONDecodeError as exc:
                raise ValueError(
                    "Memory relationship model "
                    "returned malformed JSON."
                ) from exc

            if not isinstance(
                parsed,
                dict,
            ):
                raise ValueError(
                    "Memory relationship result "
                    "must be a JSON object."
                )

            return parsed

    async def resolve(
        self,
        *,
        existing_memory: str,
        new_candidate: str,
    ) -> MemoryRelationshipResult:
        chat_service = (
            get_chat_service()
        )

        messages = [
            {
                "role": "system",
                "content": (
                    RELATIONSHIP_SYSTEM_PROMPT
                ),
            },
            {
                "role": "user",
                "content": (
                    "EXISTING MEMORY:\n"
                    f"{existing_memory}\n\n"
                    "NEW MEMORY CANDIDATE:\n"
                    f"{new_candidate}"
                ),
            },
        ]

        raw_response = (
            await chat_service
            .provider
            .generate_response(
                messages
            )
        )

        try:
            parsed = (
                self._extract_json(
                    raw_response
                )
            )

            return (
                MemoryRelationshipResult
                .model_validate(
                    parsed
                )
            )

        except (
            ValueError,
            ValidationError,
        ) as exc:
            raise RuntimeError(
                "Unable to resolve memory "
                "relationship safely."
            ) from exc


memory_relationship_service = (
    MemoryRelationshipService()
)