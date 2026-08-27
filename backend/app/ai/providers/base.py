from abc import ABC, abstractmethod


class LLMProvider(ABC):
    @abstractmethod
    async def generate_response(
        self,
        messages: list[dict[str, str]],
    ) -> str:
        """Generate a response from the configured language model."""
        raise NotImplementedError