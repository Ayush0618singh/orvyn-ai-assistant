import json
import re
from typing import Any

from pydantic import ValidationError

from app.schemas.memory_candidate import (
    MemoryCandidate,
)
from app.services.chat_service import (
    get_chat_service,
)
from app.services.memory_safety_service import (
    memory_safety_service,
)


MEMORY_EXTRACTION_SYSTEM_PROMPT = """
You are ORVYN's long-term memory candidate extraction engine.

Your job is NOT to answer the user.

Your only job is to inspect the user's message and decide whether it contains
durable information that could be useful as long-term personal memory.

Return ONLY valid JSON.

Allowed memory types:
- fact
- preference
- instruction
- profile

Do NOT create:
- notes
- tasks
- reminders
- calendar events
- temporary plans

A good long-term memory should usually be useful across future conversations.

Examples of useful memory:
- "I prefer Python for backend development."
- "I am studying MCA."
- "I usually prefer concise explanations."
- "From now on, give me complete code files."
- "My main career goal is to become an AI engineer."

Examples that should NOT become long-term memory:
- "What is FastAPI?"
- "I am drinking coffee right now."
- "Tomorrow I have to submit an assignment."
- "Search this on the web."
- "Generate a React component."
- "My OTP is 123456."
- "My password is abc123."
- "My API key is ..."
- random one-time conversation details

Never extract or store:
- passwords
- OTPs
- authentication codes
- API keys
- access tokens
- refresh tokens
- private keys
- payment card information
- banking credentials
- security secrets

Do not invent information.

The extracted content should preserve the actual meaning of what the user said.

If the message contains no useful durable memory, return:

{
  "should_remember": false,
  "memory_type": null,
  "content": null,
  "importance": 0.5,
  "confidence": 0.0,
  "reason": "..."
}

If it contains useful durable memory, return:

{
  "should_remember": true,
  "memory_type": "fact | preference | instruction | profile",
  "content": "clean durable memory statement",
  "importance": 0.0,
  "confidence": 0.0,
  "reason": "short explanation"
}

importance and confidence must be numbers between 0.0 and 1.0.

Confidence means how confident you are that this should genuinely become
long-term memory.

Return JSON only. Do not use markdown fences.
""".strip()


class AutoMemoryExtractorService:
    MIN_CONFIDENCE = 0.70

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
                    "LLM memory extraction result "
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
                    "LLM did not return valid JSON."
                )

            try:
                parsed = json.loads(
                    match.group(0)
                )
            except json.JSONDecodeError as exc:
                raise ValueError(
                    "LLM returned malformed JSON."
                ) from exc

            if not isinstance(
                parsed,
                dict,
            ):
                raise ValueError(
                    "LLM memory extraction result "
                    "must be a JSON object."
                )

            return parsed

    @staticmethod
    def _rejected_candidate(
        reason: str,
        *,
        confidence: float = 0.0,
    ) -> MemoryCandidate:
        return MemoryCandidate(
            should_remember=False,
            memory_type=None,
            content=None,
            importance=0.5,
            confidence=confidence,
            reason=reason,
        )

    async def extract_candidate(
        self,
        user_message: str,
    ) -> MemoryCandidate:
        cleaned_message = (
            " ".join(
                user_message
                .strip()
                .split()
            )
        )

        if not cleaned_message:
            return (
                self._rejected_candidate(
                    "Empty message."
                )
            )

        #
        # Safety check BEFORE sending
        # the message into the memory
        # extraction pipeline.
        #
        safety_result = (
            memory_safety_service.check(
                cleaned_message
            )
        )

        if not safety_result.allowed:
            return (
                self._rejected_candidate(
                    (
                        "Automatic memory blocked: "
                        f"{safety_result.reason}"
                    ),
                    confidence=1.0,
                )
            )

        chat_service = (
            get_chat_service()
        )

        extraction_messages = [
            {
                "role": "system",
                "content": (
                    MEMORY_EXTRACTION_SYSTEM_PROMPT
                ),
            },
            {
                "role": "user",
                "content": cleaned_message,
            },
        ]

        try:
            raw_response = (
                await chat_service
                .provider
                .generate_response(
                    extraction_messages
                )
            )
        except Exception as exc:
            return (
                self._rejected_candidate(
                    (
                        "Automatic memory extraction "
                        "could not be completed: "
                        f"{type(exc).__name__}."
                    )
                )
            )

        try:
            raw_candidate = (
                self._extract_json(
                    raw_response
                )
            )

            candidate = (
                MemoryCandidate
                .model_validate(
                    raw_candidate
                )
            )

        except (
            ValueError,
            ValidationError,
        ):
            return (
                self._rejected_candidate(
                    (
                        "The memory extraction model "
                        "returned an invalid structured "
                        "result."
                    )
                )
            )

        if not candidate.should_remember:
            return candidate

        if not candidate.content:
            return (
                self._rejected_candidate(
                    (
                        "Memory candidate was rejected "
                        "because extracted content was "
                        "empty."
                    )
                )
            )

        #
        # Safety check AGAIN after
        # extraction because the model
        # may have transformed the text.
        #
        extracted_safety = (
            memory_safety_service.check(
                candidate.content
            )
        )

        if not extracted_safety.allowed:
            return (
                self._rejected_candidate(
                    (
                        "Extracted memory was blocked: "
                        f"{extracted_safety.reason}"
                    ),
                    confidence=1.0,
                )
            )

        if (
            candidate.confidence
            < self.MIN_CONFIDENCE
        ):
            return (
                self._rejected_candidate(
                    (
                        "Memory candidate confidence "
                        "was below the automatic "
                        "memory threshold."
                    ),
                    confidence=(
                        candidate.confidence
                    ),
                )
            )

        return candidate


auto_memory_extractor_service = (
    AutoMemoryExtractorService()
)