from openai import AsyncOpenAI

from app.ai.providers.base import LLMProvider
from app.core.config import settings


class OpenAIProvider(LLMProvider):
    def __init__(self) -> None:
        if not settings.openai_api_key:
            raise ValueError(
                "OPENAI_API_KEY is not configured in backend/.env"
            )

        self.client = AsyncOpenAI(
            api_key=settings.openai_api_key,
        )

    async def generate_response(
        self,
        messages: list[dict[str, str]],
    ) -> str:
        response = await self.client.responses.create(
            model=settings.llm_model,
            input=messages,
        )

        if not response.output_text:
            raise RuntimeError(
                "OpenAI returned an empty response."
            )

        return response.output_text