
from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from typing import TypeVar

from google.genai import errors

from app.ai.providers.gemini_provider import (
    GeminiProvider,
)
from app.core.config import settings


logger = logging.getLogger(__name__)

T = TypeVar("T")

# Bounded retries prevent indefinite agent waiting.
REQUEST_TIMEOUT_SECONDS = 12.0
MAX_PRIMARY_ATTEMPTS = 2
RETRY_DELAY_SECONDS = 0.5

RETRYABLE_SERVER_CODES = {500, 502, 503, 504}


class GeminiReliabilityError(RuntimeError):
    """Safe public error for unavailable structured AI."""


class ReliableGeminiProvider(GeminiProvider):
    """
    Reliability layer for ORVYN's structured tool calls.

    Features:
    - Bounded primary attempts
    - One fallback attempt
    - Per-attempt timeout
    - Limited exponential-free backoff
    - No retries for invalid schemas/auth errors
    - No retries for non-transient client errors
    - No API keys or prompt contents in logs
    - Existing Pydantic validation remains unchanged

    Only structured tool-selection methods are overridden.
    Normal chat and streaming remain inherited.
    """

    @staticmethod
    def _retryable(exc: Exception) -> bool:
        if isinstance(exc, TimeoutError):
            return True

        if isinstance(exc, errors.ServerError):
            return (
                getattr(exc, "code", None)
                in RETRYABLE_SERVER_CODES
            )

        if isinstance(exc, errors.ClientError):
            return getattr(exc, "code", None) == 429

        return False

    @staticmethod
    def _safe_error(exc: Exception) -> str:
        if isinstance(exc, TimeoutError):
            return "timeout"

        if isinstance(exc, errors.ClientError):
            return "rate_limit"

        if isinstance(exc, errors.ServerError):
            return "server_unavailable"

        return "provider_error"

    async def _with_reliability(
        self,
        *,
        operation: Callable[[str], Awaitable[T]],
        operation_name: str,
    ) -> T:
        primary = settings.llm_model
        fallback = settings.gemini_fallback_model

        # Avoid calling the same model as its own fallback.
        models = [primary]

        if fallback and fallback != primary:
            models.append(fallback)

        last_error: Exception | None = None

        for model_index, model in enumerate(models):
            attempts = (
                MAX_PRIMARY_ATTEMPTS
                if model_index == 0
                else 1
            )

            for attempt in range(1, attempts + 1):
                try:
                    return await asyncio.wait_for(
                        operation(model),
                        timeout=REQUEST_TIMEOUT_SECONDS,
                    )

                except asyncio.CancelledError:
                    raise

                except Exception as exc:
                    # Unexpected failures and invalid
                    # requests must never be retried.
                    if not self._retryable(exc):
                        logger.warning(
                            "Gemini %s failed permanently: %s",
                            operation_name,
                            type(exc).__name__,
                        )
                        raise GeminiReliabilityError(
                            "Structured AI request failed."
                        ) from exc

                    last_error = exc

                    logger.warning(
                        "Gemini %s: model=%s "
                        "attempt=%d/%d error=%s",
                        operation_name,
                        model,
                        attempt,
                        attempts,
                        self._safe_error(exc),
                    )

                    if (
                        model_index == 0
                        and attempt < attempts
                    ):
                        await asyncio.sleep(
                            RETRY_DELAY_SECONDS
                        )

        raise GeminiReliabilityError(
            "Structured AI is temporarily unavailable."
        ) from last_error

    async def generate_structured_response(
        self,
        messages: list[dict[str, str]],
    ) -> str:
        prompt = self._build_prompt(messages)

        return await self._with_reliability(
            operation=lambda model: (
                self._generate_structured_with_model(
                    model=model,
                    prompt=prompt,
                )
            ),
            operation_name="tool_choice",
        )

    async def generate_json_with_schema(
        self,
        *,
        prompt: str,
        response_schema: dict,
    ) -> str:
        # The inherited per-model method must already
        # use the Gemini schema adapter added in the
        # previous phase.
        return await self._with_reliability(
            operation=lambda model: (
                self._generate_json_with_schema_for_model(
                    model=model,
                    prompt=prompt,
                    response_schema=response_schema,
                )
            ),
            operation_name="tool_arguments",
        )
