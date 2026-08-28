from app.ai.providers.base import LLMProvider
from app.ai.providers.gemini_provider import (
    GeminiProvider,
)
from app.ai.providers.openai_provider import (
    OpenAIProvider,
)
from app.core.config import settings
from app.schemas.chat import ChatMessage


SYSTEM_PROMPT = """
You are ORVYN, a personal multilingual AI assistant.

Respond accurately, clearly, and helpfully.

Understand the language used by the user and respond in the same language
unless the user explicitly asks for another language.

You can understand English, Hindi, Hinglish, and other languages supported
by the underlying model.

Use previous messages from the current conversation when they are relevant.

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
        conversation: list[ChatMessage],
    ) -> str:
        messages: list[
            dict[str, str]
        ] = [
            {
                "role": "system",
                "content": SYSTEM_PROMPT,
            }
        ]

        for message in conversation:
            messages.append(
                {
                    "role": message.role,
                    "content": message.content,
                }
            )

        return (
            await self.provider.generate_response(
                messages
            )
        )


def get_chat_service() -> ChatService:
    provider_name = (
        settings.llm_provider
        .lower()
        .strip()
    )

    if provider_name == "gemini":
        return ChatService(
            GeminiProvider()
        )

    if provider_name == "openai":
        return ChatService(
            OpenAIProvider()
        )

    raise ValueError(
        "Unsupported LLM provider: "
        f"{settings.llm_provider}"
    )