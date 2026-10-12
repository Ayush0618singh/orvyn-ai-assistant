from abc import ABC, abstractmethod
from collections.abc import AsyncIterator


class LLMProvider(ABC):
    @abstractmethod
    async def generate_response(
        self,
        messages: list[dict[str, str]],
    ) -> str:
        """
        Generate a complete conversational response.
        """
        raise NotImplementedError

    @abstractmethod
    def stream_response(
        self,
        messages: list[dict[str, str]],
    ) -> AsyncIterator[str]:
        """
        Stream conversational response text chunks.
        """
        raise NotImplementedError

    async def generate_structured_response(
        self,
        messages: list[dict[str, str]],
    ) -> str:
        """
        Generate a complete machine-readable response.

        Providers may override this method with native
        structured-output capabilities.

        The default implementation deliberately falls back
        to normal non-streaming generation so existing
        providers remain compatible.

        IMPORTANT:
        Provider output is still untrusted. ORVYN must
        validate it before using it for tool selection,
        permissions, approvals or execution.
        """
        return await self.generate_response(
            messages
        )