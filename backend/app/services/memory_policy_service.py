import re

from app.schemas.memory_candidate import (
    MemoryCandidate,
)


class MemoryPolicyService:
    """
    Deterministic first-pass policy for deciding whether
    a user message is even worth considering for automatic
    long-term memory extraction.

    This does not save anything to the database.
    """

    _PREFERENCE_PATTERNS: tuple[
        re.Pattern[str],
        ...
    ] = (
        re.compile(
            r"\bi prefer\b",
            re.IGNORECASE,
        ),
        re.compile(
            r"\bi like\b",
            re.IGNORECASE,
        ),
        re.compile(
            r"\bi dislike\b",
            re.IGNORECASE,
        ),
        re.compile(
            r"\bi usually prefer\b",
            re.IGNORECASE,
        ),
        re.compile(
            r"\bmy preference is\b",
            re.IGNORECASE,
        ),
        re.compile(
            r"\bmujhe .+ pasand\b",
            re.IGNORECASE,
        ),
        re.compile(
            r"\bmain .+ prefer\b",
            re.IGNORECASE,
        ),
        re.compile(
            r"\bmai .+ prefer\b",
            re.IGNORECASE,
        ),
    )

    _PROFILE_PATTERNS: tuple[
        re.Pattern[str],
        ...
    ] = (
        re.compile(
            r"\bi work as\b",
            re.IGNORECASE,
        ),
        re.compile(
            r"\bi am studying\b",
            re.IGNORECASE,
        ),
        re.compile(
            r"\bi study\b",
            re.IGNORECASE,
        ),
        re.compile(
            r"\bi am a student\b",
            re.IGNORECASE,
        ),
        re.compile(
            r"\bmy role is\b",
            re.IGNORECASE,
        ),
        re.compile(
            r"\bmy profession is\b",
            re.IGNORECASE,
        ),
        re.compile(
            r"\bmain .+ padh raha\b",
            re.IGNORECASE,
        ),
        re.compile(
            r"\bmai .+ padh raha\b",
            re.IGNORECASE,
        ),
    )

    _INSTRUCTION_PATTERNS: tuple[
        re.Pattern[str],
        ...
    ] = (
        re.compile(
            r"\balways\b",
            re.IGNORECASE,
        ),
        re.compile(
            r"\bfrom now on\b",
            re.IGNORECASE,
        ),
        re.compile(
            r"\bgoing forward\b",
            re.IGNORECASE,
        ),
        re.compile(
            r"\bin future\b",
            re.IGNORECASE,
        ),
        re.compile(
            r"\bhamesha\b",
            re.IGNORECASE,
        ),
        re.compile(
            r"\baage se\b",
            re.IGNORECASE,
        ),
    )

    _TRANSIENT_PATTERNS: tuple[
        re.Pattern[str],
        ...
    ] = (
        re.compile(
            r"\bright now\b",
            re.IGNORECASE,
        ),
        re.compile(
            r"\btoday\b",
            re.IGNORECASE,
        ),
        re.compile(
            r"\btonight\b",
            re.IGNORECASE,
        ),
        re.compile(
            r"\bthis morning\b",
            re.IGNORECASE,
        ),
        re.compile(
            r"\bthis evening\b",
            re.IGNORECASE,
        ),
        re.compile(
            r"\babhi\b",
            re.IGNORECASE,
        ),
        re.compile(
            r"\baaj\b",
            re.IGNORECASE,
        ),
    )

    def evaluate(
        self,
        text: str,
    ) -> MemoryCandidate:
        cleaned_text = (
            " ".join(
                text.strip().split()
            )
        )

        if not cleaned_text:
            return MemoryCandidate(
                should_remember=False,
                reason="Empty message.",
            )

        if len(cleaned_text) < 8:
            return MemoryCandidate(
                should_remember=False,
                reason=(
                    "Message is too short to "
                    "represent useful long-term "
                    "memory."
                ),
            )

        for pattern in (
            self._TRANSIENT_PATTERNS
        ):
            if pattern.search(
                cleaned_text
            ):
                return MemoryCandidate(
                    should_remember=False,
                    reason=(
                        "The statement appears "
                        "temporary rather than "
                        "long-term."
                    ),
                )

        for pattern in (
            self._PREFERENCE_PATTERNS
        ):
            if pattern.search(
                cleaned_text
            ):
                return MemoryCandidate(
                    should_remember=True,
                    memory_type=(
                        "preference"
                    ),
                    content=cleaned_text,
                    importance=0.7,
                    confidence=0.75,
                    reason=(
                        "The message appears to "
                        "describe a persistent user "
                        "preference."
                    ),
                )

        for pattern in (
            self._INSTRUCTION_PATTERNS
        ):
            if pattern.search(
                cleaned_text
            ):
                return MemoryCandidate(
                    should_remember=True,
                    memory_type=(
                        "instruction"
                    ),
                    content=cleaned_text,
                    importance=0.8,
                    confidence=0.7,
                    reason=(
                        "The message appears to "
                        "contain a persistent user "
                        "instruction."
                    ),
                )

        for pattern in (
            self._PROFILE_PATTERNS
        ):
            if pattern.search(
                cleaned_text
            ):
                return MemoryCandidate(
                    should_remember=True,
                    memory_type=(
                        "profile"
                    ),
                    content=cleaned_text,
                    importance=0.65,
                    confidence=0.7,
                    reason=(
                        "The message appears to "
                        "contain durable profile "
                        "information."
                    ),
                )

        return MemoryCandidate(
            should_remember=False,
            reason=(
                "No strong deterministic signal "
                "for durable long-term memory was "
                "detected."
            ),
        )


memory_policy_service = (
    MemoryPolicyService()
)