
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class DeterministicToolMatch:
    tool_name: str
    arguments: dict[str, Any]


class DeterministicToolRouter:
    """
    Conservative deterministic router for supported,
    read-only ORVYN tools.

    This router only proposes a tool and arguments.
    It does not authorize or execute tools.
    """

    _CALCULATE_PREFIX = re.compile(
        r"^\s*(?:calculate|compute|evaluate|"
        r"solve|what is|kitna hoga|kitna hai)"
        r"\s*:?\s*",
        re.IGNORECASE,
    )

    _ARITHMETIC = re.compile(
        r"^[\d\s.+*/%()\-]+$"
    )

    _TIME_REQUEST = re.compile(
        r"^(?:what(?:'s| is) the (?:current )?"
        r"(?:time|date)|"
        r"current (?:time|date)|"
        r"india me abhi (?:current )?time kya hai"
        r"|abhi india me kitne baje hain)"
        r"\s*\??$",
        re.IGNORECASE,
    )

    _CALCULATE_SUFFIX = re.compile(
        r"\s*(?:calculate karo|calculate|"
        r"compute karo|solve karo|"
        r"kitna hoga|kitna hai)\s*\??$",
        re.IGNORECASE,
    )

    _TEXT_ANALYSIS_REQUEST = re.compile(
        r"^\s*(?:"
        r"count\s+(?:the\s+)?(?:words?|characters?|sentences?)"
        r"|word\s+count"
        r"|character\s+count"
        r"|sentence\s+count"
        r"|analy[sz]e\s+(?:the\s+)?text"
        r"|text\s+analy[sz]e\s+karo"
        r"|words?\s+count\s+karo"
        r"|kitne\s+words?\s+(?:hain|hai)"
        r")\b",
        re.IGNORECASE,
    )

    _QUOTED_TEXT = re.compile(
        r"""(?P<quote>["'“‘])(?P<text>.*?)(?P<close>["'”’])""",
        re.DOTALL,
    )

    _QUOTE_PAIRS = {
        '"': '"',
        "'": "'",
        "“": "”",
        "‘": "’",
    }

    def _route_text_analysis(
        self,
        message: str,
    ) -> DeterministicToolMatch | None:
        if not self._TEXT_ANALYSIS_REQUEST.match(message):
            return None

        for match in self._QUOTED_TEXT.finditer(message):
            opening = match.group("quote")
            closing = match.group("close")

            if self._QUOTE_PAIRS.get(opening) != closing:
                continue

            text = match.group("text")

            if not text.strip():
                return None

            if len(text) > 10000:
                return None

            return DeterministicToolMatch(
                tool_name="text_analyzer",
                arguments={
                    "text": text,
                },
            )

        return None

    def route(
        self,
        user_message: str,
    ) -> DeterministicToolMatch | None:
        if not isinstance(user_message, str):
            return None

        message = user_message.strip()

        if not message or len(message) > 500:
            return None

        if self._TIME_REQUEST.fullmatch(message):
            return DeterministicToolMatch(
                tool_name="current_datetime",
                arguments={
                    "timezone": (
                        "Asia/Kolkata"
                        if "india" in message.lower()
                        else "UTC"
                    ),
                },
            )

        text_match = self._route_text_analysis(
            message
        )

        if text_match is not None:
            return text_match

        expression = self._CALCULATE_PREFIX.sub(
            "",
            message,
            count=1,
        )

        expression = self._CALCULATE_SUFFIX.sub(
            "",
            expression,
            count=1,
        ).strip()

        expression = expression.removesuffix("?").strip()

        if (
            expression
            and len(expression) <= 200
            and self._ARITHMETIC.fullmatch(expression)
            and any(
                op in expression
                for op in ("+", "-", "*", "/", "%")
            )
        ):
            return DeterministicToolMatch(
                tool_name="calculator",
                arguments={
                    "expression": expression,
                },
            )

        return None
