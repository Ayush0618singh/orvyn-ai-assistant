import asyncio
import logging

from google import genai
from google.genai import errors

from app.ai.providers.base import LLMProvider
from app.core.config import settings


logger = logging.getLogger(__name__)


class GeminiProvider(LLMProvider):
    def __init__(self) -> None:
        if not settings.gemini_api_key:
            raise ValueError(
                "GEMINI_API_KEY is not configured in backend/.env"
            )

        self.client = genai.Client(
            api_key=settings.gemini_api_key,
        )

    async def _generate_with_model(
        self,
        model: str,
        prompt: str,
    ) -> str:
        response = await self.client.aio.models.generate_content(
            model=model,
            contents=prompt,
        )

        if not response.text:
            raise RuntimeError(
                f"Gemini model {model} returned an empty response."
            )

        return response.text

    async def generate_response(
        self,
        messages: list[dict[str, str]],
    ) -> str:
        system_message = ""
        conversation_parts: list[str] = []

        for message in messages:
            role = message.get("role", "")
            content = message.get("content", "")

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
                f"System instructions:\n{system_message}"
            )

        if conversation_parts:
            prompt_parts.append(
                "\n".join(conversation_parts)
            )

        prompt = "\n\n".join(prompt_parts)

        primary_model = settings.llm_model
        fallback_model = settings.gemini_fallback_model

        retry_delays = [1, 2, 4]

        for attempt, delay in enumerate(
            retry_delays,
            start=1,
        ):
            try:
                return await self._generate_with_model(
                    model=primary_model,
                    prompt=prompt,
                )

            except errors.ServerError as exc:
                if exc.code != 503:
                    raise

                logger.warning(
                    "Gemini model %s unavailable. "
                    "Retry attempt %s/%s.",
                    primary_model,
                    attempt,
                    len(retry_delays),
                )

                await asyncio.sleep(delay)

        logger.warning(
            "Primary Gemini model %s remains unavailable. "
            "Trying fallback model %s.",
            primary_model,
            fallback_model,
        )

        return await self._generate_with_model(
            model=fallback_model,
            prompt=prompt,
        )