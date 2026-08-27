from app.ai.providers.base import LLMProvider
from app.ai.providers.gemini_provider import GeminiProvider
from app.ai.providers.openai_provider import OpenAIProvider
from app.core.config import settings


SYSTEM_PROMPT = """
You are ORVYN, a personal multilingual AI assistant.

Respond accurately, clearly, and helpfully.

Understand the language used by the user and respond in the same language
unless the user explicitly asks for another language.

You can understand English, Hindi, Hinglish, and other languages supported
by the underlying model.

Do not claim to have used tools, memory, web search, files, or external
systems unless those capabilities were actually provided to you.
""".strip()


class ChatService:
    def __init__(
        self,
        provider: LLMProvider,
    ) -> None:
        self.provider = provider

    async def chat(
        self,
        message: str,
    ) -> str:
        messages = [
            {
                "role": "system",
                "content": SYSTEM_PROMPT,
            },
            {
                "role": "user",
                "content": message,
            },
        ]

        return await self.provider.generate_response(
            messages
        )


def get_chat_service() -> ChatService:
    provider_name = settings.llm_provider.lower().strip()

    if provider_name == "gemini":
        provider = GeminiProvider()

        return ChatService(provider)

    if provider_name == "openai":
        provider = OpenAIProvider()

        return ChatService(provider)

    raise ValueError(
        f"Unsupported LLM provider: {settings.llm_provider}"
    )