from abc import (
    ABC,
    abstractmethod,
)
from dataclasses import (
    dataclass,
)


@dataclass(
    slots=True
)
class RawWebSearchResult:
    title: str

    url: str

    content: str

    provider_score: (
        float
        | None
    ) = None


class WebSearchProvider(
    ABC
):
    provider_name: str

    @abstractmethod
    async def search(
        self,
        *,
        query: str,
        max_results: int,
    ) -> list[
        RawWebSearchResult
    ]:
        raise NotImplementedError