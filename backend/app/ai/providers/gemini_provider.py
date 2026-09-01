import asyncio
import logging
from collections.abc import (
    AsyncIterator,
)

from google import genai
from google.genai import (
    errors,
    types,
)

from app.ai.providers.base import (
    LLMProvider,
)
from app.ai.types import (
    AIAttachment,
)
from app.core.config import settings


logger = logging.getLogger(
    __name__
)


class GeminiQuotaError(
    RuntimeError
):
    """Raised when Gemini API quota/rate limit is exhausted."""


class GeminiProvider(
    LLMProvider
):
    def __init__(self) -> None:
        if not settings.gemini_api_key:
            raise ValueError(
                "GEMINI_API_KEY is not configured in backend/.env"
            )

        self.client = genai.Client(
            api_key=(
                settings.gemini_api_key
            ),
        )

    @staticmethod
    def _build_prompt(
        messages: list[
            dict[str, str]
        ],
    ) -> str:
        system_message = ""

        conversation_parts: list[
            str
        ] = []

        for message in messages:
            role = message.get(
                "role",
                "",
            )

            content = message.get(
                "content",
                "",
            )

            if role == "system":
                system_message = (
                    content
                )

            elif role == "user":
                conversation_parts.append(
                    f"User: {content}"
                )

            elif role == "assistant":
                conversation_parts.append(
                    f"Assistant: {content}"
                )

        prompt_parts: list[
            str
        ] = []

        if system_message:
            prompt_parts.append(
                "System instructions:\n"
                f"{system_message}"
            )

        if conversation_parts:
            prompt_parts.append(
                "\n".join(
                    conversation_parts
                )
            )

        return "\n\n".join(
            prompt_parts
        )

    @staticmethod
    def _build_contents(
        prompt: str,
        attachments: list[
            AIAttachment
        ] | None = None,
    ):
        parts: list[
            types.Part
        ] = [
            types.Part.from_text(
                text=prompt
            )
        ]

        for attachment in (
            attachments or []
        ):
            if (
                attachment.mime_type
                == "text/plain"
            ):
                text = (
                    attachment.data
                    .decode(
                        "utf-8"
                    )
                )

                parts.append(
                    types.Part.from_text(
                        text=(
                            "\n\n"
                            f"Attached text file: "
                            f"{attachment.filename}\n"
                            "-----\n"
                            f"{text}\n"
                            "-----"
                        )
                    )
                )

                continue

            parts.append(
                types.Part.from_bytes(
                    data=(
                        attachment.data
                    ),
                    mime_type=(
                        attachment.mime_type
                    ),
                )
            )

        return parts

    @staticmethod
    def _is_quota_error(
        exc: Exception,
    ) -> bool:
        return (
            isinstance(
                exc,
                errors.ClientError,
            )
            and getattr(
                exc,
                "code",
                None,
            )
            == 429
        )

    async def _generate_with_model(
        self,
        model: str,
        prompt: str,
        attachments: list[
            AIAttachment
        ] | None = None,
    ) -> str:
        response = (
            await self.client
            .aio
            .models
            .generate_content(
                model=model,
                contents=(
                    self._build_contents(
                        prompt,
                        attachments,
                    )
                ),
            )
        )

        if not response.text:
            raise RuntimeError(
                f"Gemini model {model} returned an empty response."
            )

        return response.text

    async def _generate_with_fallback(
        self,
        prompt: str,
        attachments: list[
            AIAttachment
        ] | None = None,
    ) -> str:
        primary_model = (
            settings.llm_model
        )

        fallback_model = (
            settings.gemini_fallback_model
        )

        retry_delays = [
            1,
            2,
            4,
        ]

        for attempt, delay in enumerate(
            retry_delays,
            start=1,
        ):
            try:
                return await (
                    self._generate_with_model(
                        model=(
                            primary_model
                        ),
                        prompt=prompt,
                        attachments=(
                            attachments
                        ),
                    )
                )

            except errors.ClientError as exc:
                if not self._is_quota_error(
                    exc
                ):
                    raise

                logger.warning(
                    "Gemini primary model %s hit quota limit. "
                    "Trying fallback model %s.",
                    primary_model,
                    fallback_model,
                )

                break

            except errors.ServerError as exc:
                if exc.code != 503:
                    raise

                logger.warning(
                    "Gemini model %s unavailable. Retry attempt %s/%s.",
                    primary_model,
                    attempt,
                    len(
                        retry_delays
                    ),
                )

                await asyncio.sleep(
                    delay
                )

        try:
            return await (
                self._generate_with_model(
                    model=fallback_model,
                    prompt=prompt,
                    attachments=(
                        attachments
                    ),
                )
            )

        except errors.ClientError as exc:
            if self._is_quota_error(
                exc
            ):
                raise GeminiQuotaError(
                    "Gemini free-tier quota has been reached. "
                    "Please try again later."
                ) from exc

            raise

        except errors.ServerError as exc:
            if exc.code == 503:
                raise RuntimeError(
                    "Gemini is temporarily unavailable. "
                    "Please try again shortly."
                ) from exc

            raise

    async def generate_response(
        self,
        messages: list[
            dict[str, str]
        ],
    ) -> str:
        return await (
            self._generate_with_fallback(
                self._build_prompt(
                    messages
                )
            )
        )

    async def generate_multimodal_response(
        self,
        messages: list[
            dict[str, str]
        ],
        attachments: list[
            AIAttachment
        ],
    ) -> str:
        return await (
            self._generate_with_fallback(
                self._build_prompt(
                    messages
                ),
                attachments,
            )
        )

    async def _stream_with_model(
        self,
        model: str,
        prompt: str,
        attachments: list[
            AIAttachment
        ] | None = None,
    ) -> AsyncIterator[str]:
        stream = (
            await self.client
            .aio
            .models
            .generate_content_stream(
                model=model,
                contents=(
                    self._build_contents(
                        prompt,
                        attachments,
                    )
                ),
            )
        )

        async for chunk in stream:
            text = chunk.text

            if text:
                yield text

    async def _stream_with_fallback(
        self,
        prompt: str,
        attachments: list[
            AIAttachment
        ] | None = None,
    ) -> AsyncIterator[str]:
        primary_model = (
            settings.llm_model
        )

        fallback_model = (
            settings.gemini_fallback_model
        )

        retry_delays = [
            1,
            2,
            4,
        ]

        should_try_fallback = False

        for attempt, delay in enumerate(
            retry_delays,
            start=1,
        ):
            yielded_any_chunk = (
                False
            )

            try:
                async for chunk in (
                    self._stream_with_model(
                        model=(
                            primary_model
                        ),
                        prompt=prompt,
                        attachments=(
                            attachments
                        ),
                    )
                ):
                    yielded_any_chunk = (
                        True
                    )

                    yield chunk

                return

            except errors.ClientError as exc:
                if not self._is_quota_error(
                    exc
                ):
                    raise

                if yielded_any_chunk:
                    raise GeminiQuotaError(
                        "Gemini quota was reached while generating "
                        "the response."
                    ) from exc

                should_try_fallback = (
                    True
                )

                break

            except errors.ServerError as exc:
                if exc.code != 503:
                    raise

                if yielded_any_chunk:
                    raise RuntimeError(
                        "Gemini connection was interrupted while "
                        "generating the response."
                    ) from exc

                logger.warning(
                    "Gemini streaming model %s unavailable. "
                    "Retry attempt %s/%s.",
                    primary_model,
                    attempt,
                    len(
                        retry_delays
                    ),
                )

                await asyncio.sleep(
                    delay
                )

        if not should_try_fallback:
            logger.warning(
                "Primary Gemini streaming model %s remains unavailable. "
                "Trying fallback model %s.",
                primary_model,
                fallback_model,
            )

        try:
            async for chunk in (
                self._stream_with_model(
                    model=(
                        fallback_model
                    ),
                    prompt=prompt,
                    attachments=(
                        attachments
                    ),
                )
            ):
                yield chunk

        except errors.ClientError as exc:
            if self._is_quota_error(
                exc
            ):
                raise GeminiQuotaError(
                    "Gemini free-tier quota has been reached. "
                    "Please try again later."
                ) from exc

            raise

        except errors.ServerError as exc:
            if exc.code == 503:
                raise RuntimeError(
                    "Gemini is temporarily unavailable. "
                    "Please try again shortly."
                ) from exc

            raise

    async def stream_response(
        self,
        messages: list[
            dict[str, str]
        ],
    ) -> AsyncIterator[str]:
        async for chunk in (
            self._stream_with_fallback(
                self._build_prompt(
                    messages
                )
            )
        ):
            yield chunk

    async def stream_multimodal_response(
        self,
        messages: list[
            dict[str, str]
        ],
        attachments: list[
            AIAttachment
        ],
    ) -> AsyncIterator[str]:
        async for chunk in (
            self._stream_with_fallback(
                self._build_prompt(
                    messages
                ),
                attachments,
            )
        ):
            yield chunk