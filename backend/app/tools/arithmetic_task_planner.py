"""ORVYN: Conservative two-step arithmetic task planner.

Supports explicitly recognized English and Hinglish arithmetic requests.

Security:
- No eval, exec, shell, network or LLM-generated instructions.
- Strict input length and expression allowlist.
- Exactly two supported clauses.
- Unsupported or ambiguous requests return None.
"""

from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation

from app.tools.multi_step_engine import ArithmeticPlan, Step


class ArithmeticTaskPlanner:
    MAX_MESSAGE_LENGTH = 500
    MAX_EXPRESSION_LENGTH = 180

    _NUMBER = r"\d+(?:\.\d+)?"
    _PERCENT = r"\d{1,3}(?:\.\d{1,2})?"

    _EXPRESSION = re.compile(r"^[0-9+\-*/().% \t]+$")

    _FIRST_HINGLISH = re.compile(
        r"^\s*(?P<expression>.+?)"
        r"\s+calculate\s+karo\s*$",
        re.IGNORECASE,
    )

    _FIRST_ENGLISH = re.compile(
        r"^\s*(?:calculate|compute)\s+"
        r"(?P<expression>.+?)\s*$",
        re.IGNORECASE,
    )

    _FIRST_HINGLISH_MULTIPLY = re.compile(
        rf"^\s*(?P<left>{_NUMBER})"
        rf"\s+ko\s+(?P<right>{_NUMBER})"
        r"\s+se\s+multiply\s+karo\s*$",
        re.IGNORECASE,
    )

    _MULTIPLY_WORDS = re.compile(
        rf"^\s*(?P<left>{_NUMBER})"
        r"\s+(?:multiplied\s+by|times)\s+"
        rf"(?P<right>{_NUMBER})\s*$",
        re.IGNORECASE,
    )

    _SECOND_HINGLISH = re.compile(
        rf"^\s*(?:phir|fir)\s+"
        r"(?:us\s+)?result\s+ka\s+"
        rf"(?P<percentage>{_PERCENT})"
        r"\s*(?:%|percent)"
        r"\s*(?:nikalo|nikaalo)\s*$",
        re.IGNORECASE,
    )

    _SECOND_ENGLISH = re.compile(
        r"^\s*then\s+"
        r"(?:find|calculate|compute)\s+"
        rf"(?P<percentage>{_PERCENT})"
        r"\s*(?:%|percent)\s+of\s+"
        r"(?:that\s+|the\s+)?result\s*$",
        re.IGNORECASE,
    )

    def _parse_first(self, text: str) -> str | None:
        match = self._FIRST_HINGLISH_MULTIPLY.fullmatch(text)

        if match:
            expression = (
                f"{match.group('left')} * {match.group('right')}"
            )
        else:
            match = (
                self._FIRST_HINGLISH.fullmatch(text)
                or self._FIRST_ENGLISH.fullmatch(text)
            )

            if match is None:
                return None

            expression = match.group("expression").strip()

            words = self._MULTIPLY_WORDS.fullmatch(expression)

            if words:
                expression = (
                    f"{words.group('left')} * "
                    f"{words.group('right')}"
                )

        if not expression:
            return None

        if len(expression) > self.MAX_EXPRESSION_LENGTH:
            return None

        if not self._EXPRESSION.fullmatch(expression):
            return None

        if not any(
            operator in expression
            for operator in ("+", "-", "*", "/", "%")
        ):
            return None

        return expression

    def _parse_second(self, text: str) -> str | None:
        match = (
            self._SECOND_HINGLISH.fullmatch(text)
            or self._SECOND_ENGLISH.fullmatch(text)
        )

        if match is None:
            return None

        percentage_text = match.group("percentage")

        try:
            percentage = Decimal(percentage_text)
        except InvalidOperation:
            return None

        if not percentage.is_finite():
            return None

        if not (0 <= percentage <= 100):
            return None

        return percentage_text

    def plan(
        self,
        user_message: str,
    ) -> ArithmeticPlan | None:
        if not isinstance(user_message, str):
            return None

        message = user_message.strip()

        if not message:
            return None

        if len(message) > self.MAX_MESSAGE_LENGTH:
            return None

        # Allow exactly one trailing sentence period.
        if message.endswith("."):
            message = message[:-1].rstrip()

        # Never silently ignore extra clauses.
        parts = re.split(r"\s*,\s*", message)

        if len(parts) != 2:
            return None

        first_expression = self._parse_first(parts[0])

        if first_expression is None:
            return None

        percentage = self._parse_second(parts[1])

        if percentage is None:
            return None

        return ArithmeticPlan(
            steps=[
                Step(
                    id="base",
                    expression=first_expression,
                ),
                Step(
                    id="percentage",
                    expression=f"$base * {percentage} / 100",
                ),
            ]
        )


arithmetic_task_planner = ArithmeticTaskPlanner()