from abc import ABC, abstractmethod
from collections.abc import AsyncIterator


class LLMProvider(ABC):
    @abstractmethod
    async def generate_response(
        self,
        messages: list[dict[str, str]],
    ) -> str:
        """Generate a complete response from the language model."""
        raise NotImplementedError

    @abstractmethod
    def stream_response(
        self,
        messages: list[dict[str, str]],
    ) -> AsyncIterator[str]:
        """Stream response text chunks from the language model."""
        raise NotImplementedError