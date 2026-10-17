
"""ORVYN Phase 10J-E1: bounded multi-step arithmetic execution.

Security properties:
- Validated arithmetic plans and step references.
- Execution through the existing AgentToolRunner.
- Calculator-only verified tool results.
- Maximum five steps (ArithmeticPlan).
- A deadline for the entire plan, not each individual step.
- Fail-closed behavior on errors and timeouts.
- Cooperative task cancellation is propagated, not suppressed.

This engine does not grant permissions or enable arbitrary tools.
"""

from __future__ import annotations

import asyncio
import math
import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Protocol
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


DEFAULT_PLAN_TIMEOUT_SECONDS = 10.0
MAX_PLAN_TIMEOUT_SECONDS = 30.0


class Step(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str = Field(pattern=r"^[a-z][a-z0-9_]{0,31}$")
    expression: str = Field(min_length=1, max_length=256)


class ArithmeticPlan(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    steps: list[Step] = Field(min_length=1, max_length=5)

    @model_validator(mode="after")
    def unique_ids(self):
        ids = [step.id for step in self.steps]

        if len(ids) != len(set(ids)):
            raise ValueError(
                "Duplicate step identifiers are forbidden"
            )

        return self


@dataclass(frozen=True)
class StepRecord:
    step_id: str
    expression: str
    result: str
    execution_id: str


@dataclass(frozen=True)
class PlanResult:
    status: str
    records: tuple[StepRecord, ...]
    final_result: str | None
    message: str


class Runner(Protocol):
    async def run(self, **kwargs): ...


_REF = re.compile(r"\$([a-z][a-z0-9_]{0,31})")
_ALLOWED = re.compile(r"^[0-9eE+*/().%\s-]+$")
_NUMBER = re.compile(
    r"^-?(?:\d+)(?:\.\d+)?(?:[eE][+-]?\d+)?$"
)


class SecureMultiStepEngine:
    def __init__(
        self,
        runner: Runner,
        *,
        timeout_seconds: float = DEFAULT_PLAN_TIMEOUT_SECONDS,
    ):
        if isinstance(timeout_seconds, bool):
            raise ValueError(
                "Plan timeout must be a finite positive number"
            )

        try:
            timeout = float(timeout_seconds)
        except (TypeError, ValueError, OverflowError) as exc:
            raise ValueError(
                "Plan timeout must be a finite positive number"
            ) from exc

        if (
            not math.isfinite(timeout)
            or timeout <= 0
            or timeout > MAX_PLAN_TIMEOUT_SECONDS
        ):
            raise ValueError(
                "Plan timeout must be greater than zero "
                f"and at most {MAX_PLAN_TIMEOUT_SECONDS} seconds"
            )

        self._runner = runner
        self._timeout_seconds = timeout

    @staticmethod
    def _resolve(
        expression: str,
        values: dict[str, str],
    ) -> str:
        def replace(match: re.Match[str]) -> str:
            key = match.group(1)

            if key not in values:
                raise ValueError(
                    "Unknown or forward step reference"
                )

            return f"({values[key]})"

        resolved = _REF.sub(replace, expression)

        if (
            "$" in resolved
            or not _ALLOWED.fullmatch(resolved)
        ):
            raise ValueError(
                "Expression contains unsupported characters"
            )

        return resolved

    @staticmethod
    def _validate_references(
        plan: ArithmeticPlan,
    ) -> None:
        known: dict[str, str] = {}

        for step in plan.steps:
            preview = _REF.sub(
                lambda match: (
                    "(1)"
                    if match.group(1) in known
                    else "?"
                ),
                step.expression,
            )

            if (
                "$" in preview
                or not _ALLOWED.fullmatch(preview)
            ):
                raise ValueError(
                    "Invalid or forward reference in plan"
                )

            known[step.id] = "1"

    @staticmethod
    def _validate_tool_result(outcome) -> str:
        execution = getattr(
            outcome,
            "execution",
            None,
        )

        selection = getattr(
            outcome,
            "selection",
            None,
        )

        tool_name = getattr(
            selection,
            "tool_name",
            None,
        )

        if (
            getattr(outcome, "status", None) != "succeeded"
            or execution is None
            or tool_name != "calculator"
            or getattr(
                execution,
                "tool_name",
                None,
            ) != "calculator"
            or not isinstance(
                getattr(execution, "output", None),
                dict,
            )
        ):
            raise ValueError(
                "Tool execution did not succeed"
            )

        raw_result = execution.output.get("result")

        if (
            isinstance(raw_result, bool)
            or not isinstance(
                raw_result,
                (str, int, float),
            )
        ):
            raise ValueError(
                "Tool returned an invalid numeric result"
            )

        result = str(raw_result)

        if len(result) > 80:
            raise ValueError(
                "Tool result exceeds allowed size"
            )

        if not _NUMBER.fullmatch(result):
            raise ValueError(
                "Tool returned an invalid number"
            )

        try:
            if not Decimal(result).is_finite():
                raise ValueError(
                    "Tool returned a non-finite result"
                )
        except InvalidOperation as exc:
            raise ValueError(
                "Tool returned an invalid number"
            ) from exc

        return result

    async def execute(
        self,
        *,
        plan: ArithmeticPlan,
        user_id: UUID,
        conversation_id: UUID | None = None,
        message_id: UUID | None = None,
    ) -> PlanResult:
        if not isinstance(user_id, UUID):
            raise TypeError(
                "Authenticated user_id must be a UUID"
            )

        if (
            conversation_id is not None
            and not isinstance(conversation_id, UUID)
        ):
            raise TypeError(
                "conversation_id must be a UUID"
            )

        if (
            message_id is not None
            and not isinstance(message_id, UUID)
        ):
            raise TypeError(
                "message_id must be a UUID"
            )

        if not isinstance(plan, ArithmeticPlan):
            raise TypeError(
                "plan must be a validated ArithmeticPlan"
            )

        # Reject malformed references before any tool call.
        self._validate_references(plan)

        values: dict[str, str] = {}
        records: list[StepRecord] = []

        try:
            # One deadline covers the entire plan.
            async with asyncio.timeout(
                self._timeout_seconds
            ):
                for step in plan.steps:
                    expression = self._resolve(
                        step.expression,
                        values,
                    )

                    try:
                        outcome = await self._runner.run(
                            user_message=(
                                f"{expression} calculate karo"
                            ),
                            user_id=user_id,
                            conversation_id=conversation_id,
                            message_id=message_id,
                            granted_permissions=[],
                        )

                        result = self._validate_tool_result(
                            outcome
                        )

                        execution = outcome.execution

                        values[step.id] = result

                        records.append(
                            StepRecord(
                                step_id=step.id,
                                expression=expression,
                                result=result,
                                execution_id=str(
                                    execution.execution_id
                                ),
                            )
                        )

                    except asyncio.CancelledError:
                        # Preserve cancellation from callers.
                        raise

                    except Exception:
                        # Stop immediately; do not run later steps.
                        return PlanResult(
                            status="failed",
                            records=tuple(records),
                            final_result=None,
                            message=(
                                "The plan stopped because "
                                "a step could not be verified."
                            ),
                        )

        except TimeoutError:
            return PlanResult(
                status="failed",
                records=tuple(records),
                final_result=None,
                message=(
                    "The calculation exceeded its "
                    "execution time limit."
                ),
            )

        return PlanResult(
            status="succeeded",
            records=tuple(records),
            final_result=records[-1].result,
            message=(
                "All steps completed through "
                "the verified calculator tool."
            ),
        )
