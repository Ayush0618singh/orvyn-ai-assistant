import asyncio
import logging
from collections.abc import AsyncIterator

from google import genai
from google.genai import errors, types

from app.ai.providers.base import LLMProvider
from app.ai.types import AIAttachment
from app.core.config import settings


logger = logging.getLogger(__name__)


# Tool selection is part of ORVYN's control plane.
# It must never block the agent indefinitely.
STRUCTURED_REQUEST_TIMEOUT_SECONDS = 20


# Stage 1 only decides whether a tool is required and
# which enabled tool should be proposed.
#
# Tool arguments are deliberately NOT generated here.
# They are generated separately against the selected
# tool's exact input schema.
GEMINI_TOOL_SELECTION_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "use_tool": {
            "type": "BOOLEAN",
        },
        "tool_name": {
            "type": "STRING",
            "nullable": True,
            "enum": [
                "calculator",
                "current_datetime",
            ],
        },
        "confidence": {
            "type": "NUMBER",
            "minimum": 0.0,
            "maximum": 1.0,
        },
        "reason": {
            "type": "STRING",
        },
    },
    "required": [
        "use_tool",
        "tool_name",
        "confidence",
        "reason",
    ],
}


class GeminiQuotaError(RuntimeError):
    """
    Raised when Gemini API quota or rate limit is exhausted.
    """


class GeminiProvider(LLMProvider):
    def __init__(self) -> None:
        if not settings.gemini_api_key:
            raise ValueError(
                "GEMINI_API_KEY is not configured in backend/.env"
            )

        self.client = genai.Client(
            api_key=settings.gemini_api_key,
        )

    @staticmethod
    def _build_prompt(
        messages: list[dict[str, str]],
    ) -> str:
        system_message = ""
        conversation_parts: list[str] = []

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
                system_message = content

            elif role == "user":
                conversation_parts.append(
                    f"User: {content}"
                )

            elif role == "assistant":
                conversation_parts.append(
                    f"Assistant: {content}"
                )

        prompt_parts: list[str] = []

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
        attachments: list[AIAttachment] | None = None,
    ) -> list[types.Part]:
        parts: list[types.Part] = [
            types.Part.from_text(
                text=prompt
            )
        ]

        for attachment in attachments or []:
            if attachment.mime_type == "text/plain":
                text = attachment.data.decode(
                    "utf-8"
                )

                parts.append(
                    types.Part.from_text(
                        text=(
                            "\n\n"
                            "Attached text file: "
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
                    data=attachment.data,
                    mime_type=attachment.mime_type,
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

    # =========================================================
    # NORMAL NON-STREAMING GENERATION
    # =========================================================

    async def _generate_with_model(
        self,
        model: str,
        prompt: str,
        attachments: list[AIAttachment] | None = None,
    ) -> str:
        response = (
            await self.client
            .aio
            .models
            .generate_content(
                model=model,
                contents=self._build_contents(
                    prompt,
                    attachments,
                ),
            )
        )

        if not response.text:
            raise RuntimeError(
                (
                    f"Gemini model {model} "
                    "returned an empty response."
                )
            )

        return response.text

    async def _generate_with_fallback(
        self,
        prompt: str,
        attachments: list[AIAttachment] | None = None,
    ) -> str:
        primary_model = settings.llm_model

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
                return await self._generate_with_model(
                    model=primary_model,
                    prompt=prompt,
                    attachments=attachments,
                )

            except errors.ClientError as exc:
                if not self._is_quota_error(
                    exc
                ):
                    raise

                logger.warning(
                    (
                        "Gemini primary model %s hit "
                        "quota limit. Trying fallback "
                        "model %s."
                    ),
                    primary_model,
                    fallback_model,
                )

                break

            except errors.ServerError as exc:
                if exc.code != 503:
                    raise

                logger.warning(
                    (
                        "Gemini model %s unavailable. "
                        "Retry attempt %s/%s."
                    ),
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
            return await self._generate_with_model(
                model=fallback_model,
                prompt=prompt,
                attachments=attachments,
            )

        except errors.ClientError as exc:
            if self._is_quota_error(
                exc
            ):
                raise GeminiQuotaError(
                    (
                        "Gemini free-tier quota has "
                        "been reached. Please try "
                        "again later."
                    )
                ) from exc

            raise

        except errors.ServerError as exc:
            if exc.code == 503:
                raise RuntimeError(
                    (
                        "Gemini is temporarily "
                        "unavailable. Please try "
                        "again shortly."
                    )
                ) from exc

            raise

    # =========================================================
    # STRUCTURED CONTROL-PLANE GENERATION
    # =========================================================

    async def _generate_structured_with_model(
        self,
        model: str,
        prompt: str,
    ) -> str:
        """
        Stage-1 structured generation.

        This stage only decides whether a tool is required
        and which tool should be proposed.

        Tool arguments are generated separately against
        the selected tool's exact input schema.
        """

        response = (
            await self.client
            .aio
            .models
            .generate_content(
                model=model,
                contents=self._build_contents(
                    prompt
                ),
                config=types.GenerateContentConfig(
                    response_mime_type=(
                        "application/json"
                    ),
                    response_schema=(
                        GEMINI_TOOL_SELECTION_SCHEMA
                    ),
                    temperature=0.0,
                ),
            )
        )

        if not response.text:
            raise RuntimeError(
                (
                    f"Gemini model {model} returned "
                    "an empty structured response."
                )
            )

        return response.text

    async def _generate_structured_with_fallback(
        self,
        prompt: str,
    ) -> str:
        """
        Generate stage-1 structured output using the
        primary Gemini model with bounded retries and
        then the configured fallback model.
        """

        primary_model = settings.llm_model

        fallback_model = (
            settings.gemini_fallback_model
        )

        retry_delays = [
            1,
            2,
        ]

        for attempt, delay in enumerate(
            retry_delays,
            start=1,
        ):
            try:
                return await asyncio.wait_for(
                    self._generate_structured_with_model(
                        model=primary_model,
                        prompt=prompt,
                    ),
                    timeout=(
                        STRUCTURED_REQUEST_TIMEOUT_SECONDS
                    ),
                )

            except TimeoutError:
                logger.warning(
                    (
                        "Gemini structured model %s "
                        "timed out. Attempt %s/%s."
                    ),
                    primary_model,
                    attempt,
                    len(
                        retry_delays
                    ),
                )

                if attempt < len(
                    retry_delays
                ):
                    await asyncio.sleep(
                        delay
                    )

            except errors.ClientError as exc:
                if not self._is_quota_error(
                    exc
                ):
                    raise

                logger.warning(
                    (
                        "Gemini structured primary "
                        "model %s hit quota limit. "
                        "Trying fallback model %s."
                    ),
                    primary_model,
                    fallback_model,
                )

                break

            except errors.ServerError as exc:
                if exc.code != 503:
                    raise

                logger.warning(
                    (
                        "Gemini structured model %s "
                        "unavailable. Attempt %s/%s."
                    ),
                    primary_model,
                    attempt,
                    len(
                        retry_delays
                    ),
                )

                if attempt < len(
                    retry_delays
                ):
                    await asyncio.sleep(
                        delay
                    )

        try:
            return await asyncio.wait_for(
                self._generate_structured_with_model(
                    model=fallback_model,
                    prompt=prompt,
                ),
                timeout=(
                    STRUCTURED_REQUEST_TIMEOUT_SECONDS
                ),
            )

        except TimeoutError as exc:
            raise RuntimeError(
                (
                    "Gemini structured tool "
                    "selection timed out."
                )
            ) from exc

        except errors.ClientError as exc:
            if self._is_quota_error(
                exc
            ):
                raise GeminiQuotaError(
                    (
                        "Gemini free-tier quota has "
                        "been reached. Please try "
                        "again later."
                    )
                ) from exc

            raise

        except errors.ServerError as exc:
            if exc.code == 503:
                raise RuntimeError(
                    (
                        "Gemini is temporarily "
                        "unavailable. Please try "
                        "again shortly."
                    )
                ) from exc

            raise

    # =========================================================
    # DYNAMIC STRUCTURED JSON GENERATION
    # =========================================================

    async def _generate_json_with_schema_for_model(
        self,
        *,
        model: str,
        prompt: str,
        response_schema: dict,
    ) -> str:
        """
        Generate JSON against a caller-provided schema.

        This is used after a tool has already been selected,
        so Gemini receives the exact input schema of only
        that tool.

        The output remains untrusted and must still pass
        ORVYN's deterministic Pydantic validation.
        """

        response = (
            await self.client
            .aio
            .models
            .generate_content(
                model=model,
                contents=self._build_contents(
                    prompt
                ),
                config=types.GenerateContentConfig(
                    response_mime_type=(
                        "application/json"
                    ),
                    response_schema=response_schema,
                    temperature=0.0,
                ),
            )
        )

        if not response.text:
            raise RuntimeError(
                (
                    f"Gemini model {model} returned "
                    "an empty JSON-schema response."
                )
            )

        return response.text

    async def generate_json_with_schema(
        self,
        *,
        prompt: str,
        response_schema: dict,
    ) -> str:
        """
        Public dynamic-schema generation method.

        Primary model is attempted first with a bounded
        timeout. If quota, temporary server failure or
        timeout prevents completion, ORVYN can use the
        configured fallback model.

        This method never executes a tool.
        """

        primary_model = settings.llm_model

        fallback_model = (
            settings.gemini_fallback_model
        )

        retry_delays = [
            1,
            2,
        ]

        for attempt, delay in enumerate(
            retry_delays,
            start=1,
        ):
            try:
                return await asyncio.wait_for(
                    self._generate_json_with_schema_for_model(
                        model=primary_model,
                        prompt=prompt,
                        response_schema=response_schema,
                    ),
                    timeout=(
                        STRUCTURED_REQUEST_TIMEOUT_SECONDS
                    ),
                )

            except TimeoutError:
                logger.warning(
                    (
                        "Gemini JSON-schema model %s "
                        "timed out. Attempt %s/%s."
                    ),
                    primary_model,
                    attempt,
                    len(
                        retry_delays
                    ),
                )

                if attempt < len(
                    retry_delays
                ):
                    await asyncio.sleep(
                        delay
                    )

            except errors.ClientError as exc:
                if not self._is_quota_error(
                    exc
                ):
                    raise

                logger.warning(
                    (
                        "Gemini JSON-schema primary "
                        "model %s hit quota limit. "
                        "Trying fallback model %s."
                    ),
                    primary_model,
                    fallback_model,
                )

                break

            except errors.ServerError as exc:
                if exc.code != 503:
                    raise

                logger.warning(
                    (
                        "Gemini JSON-schema model %s "
                        "unavailable. Attempt %s/%s."
                    ),
                    primary_model,
                    attempt,
                    len(
                        retry_delays
                    ),
                )

                if attempt < len(
                    retry_delays
                ):
                    await asyncio.sleep(
                        delay
                    )

        try:
            return await asyncio.wait_for(
                self._generate_json_with_schema_for_model(
                    model=fallback_model,
                    prompt=prompt,
                    response_schema=response_schema,
                ),
                timeout=(
                    STRUCTURED_REQUEST_TIMEOUT_SECONDS
                ),
            )

        except TimeoutError as exc:
            raise RuntimeError(
                (
                    "Gemini dynamic structured "
                    "generation timed out."
                )
            ) from exc

        except errors.ClientError as exc:
            if self._is_quota_error(
                exc
            ):
                raise GeminiQuotaError(
                    (
                        "Gemini free-tier quota has "
                        "been reached. Please try "
                        "again later."
                    )
                ) from exc

            raise

        except errors.ServerError as exc:
            if exc.code == 503:
                raise RuntimeError(
                    (
                        "Gemini is temporarily "
                        "unavailable. Please try "
                        "again shortly."
                    )
                ) from exc

            raise

    # =========================================================
    # PUBLIC NON-STREAMING METHODS
    # =========================================================

    async def generate_response(
        self,
        messages: list[dict[str, str]],
    ) -> str:
        return await self._generate_with_fallback(
            self._build_prompt(
                messages
            )
        )

    async def generate_structured_response(
        self,
        messages: list[dict[str, str]],
    ) -> str:
        """
        Generate machine-readable stage-1 JSON output.

        Used by ORVYN's deterministic control plane for
        tool choice. Tool arguments are handled separately.
        """

        return await (
            self._generate_structured_with_fallback(
                self._build_prompt(
                    messages
                )
            )
        )

    async def generate_multimodal_response(
        self,
        messages: list[dict[str, str]],
        attachments: list[AIAttachment],
    ) -> str:
        return await self._generate_with_fallback(
            self._build_prompt(
                messages
            ),
            attachments,
        )

    # =========================================================
    # STREAMING GENERATION
    # =========================================================

    async def _stream_with_model(
        self,
        model: str,
        prompt: str,
        attachments: list[AIAttachment] | None = None,
    ) -> AsyncIterator[str]:
        stream = (
            await self.client
            .aio
            .models
            .generate_content_stream(
                model=model,
                contents=self._build_contents(
                    prompt,
                    attachments,
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
        attachments: list[AIAttachment] | None = None,
    ) -> AsyncIterator[str]:
        primary_model = settings.llm_model

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
            yielded_any_chunk = False

            try:
                async for chunk in (
                    self._stream_with_model(
                        model=primary_model,
                        prompt=prompt,
                        attachments=attachments,
                    )
                ):
                    yielded_any_chunk = True
                    yield chunk

                return

            except errors.ClientError as exc:
                if not self._is_quota_error(
                    exc
                ):
                    raise

                if yielded_any_chunk:
                    raise GeminiQuotaError(
                        (
                            "Gemini quota was reached "
                            "while generating the response."
                        )
                    ) from exc

                should_try_fallback = True

                break

            except errors.ServerError as exc:
                if exc.code != 503:
                    raise

                if yielded_any_chunk:
                    raise RuntimeError(
                        (
                            "Gemini connection was "
                            "interrupted while generating "
                            "the response."
                        )
                    ) from exc

                logger.warning(
                    (
                        "Gemini streaming model %s "
                        "unavailable. Retry attempt %s/%s."
                    ),
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
                (
                    "Primary Gemini streaming model %s "
                    "remains unavailable. Trying fallback "
                    "model %s."
                ),
                primary_model,
                fallback_model,
            )

        try:
            async for chunk in (
                self._stream_with_model(
                    model=fallback_model,
                    prompt=prompt,
                    attachments=attachments,
                )
            ):
                yield chunk

        except errors.ClientError as exc:
            if self._is_quota_error(
                exc
            ):
                raise GeminiQuotaError(
                    (
                        "Gemini free-tier quota has "
                        "been reached. Please try "
                        "again later."
                    )
                ) from exc

            raise

        except errors.ServerError as exc:
            if exc.code == 503:
                raise RuntimeError(
                    (
                        "Gemini is temporarily "
                        "unavailable. Please try "
                        "again shortly."
                    )
                ) from exc

            raise

    # =========================================================
    # PUBLIC STREAMING METHODS
    # =========================================================

    async def stream_response(
        self,
        messages: list[dict[str, str]],
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
        messages: list[dict[str, str]],
        attachments: list[AIAttachment],
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