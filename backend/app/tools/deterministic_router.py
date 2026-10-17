
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
    Conservative router for explicitly supported,
    read-only ORVYN tools.

    Never authorizes or executes a tool.
    Never accepts permissions from user text.
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
                    "timezone": "Asia/Kolkata"
                    if "india" in message.lower()
                    else "UTC"
                },
            )

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
