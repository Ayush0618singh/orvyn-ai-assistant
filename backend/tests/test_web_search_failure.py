import pytest

from app.services.web_search_service import (
    WebSearchService,
)


class FailingSearchProvider:
    """
    Controlled fake provider used only for testing.

    It simulates an external search provider outage
    without making a real network request.
    """

    name = "failing-test-provider"

    async def search(
        self,
        query: str,
        max_results: int,
    ):
        raise RuntimeError(
            "Simulated external provider failure."
        )


@pytest.mark.asyncio
async def test_provider_failure_is_not_silently_converted_to_fake_results():
    service = WebSearchService(
        provider=FailingSearchProvider()
    )

    with pytest.raises(
        RuntimeError,
        match=(
            "Simulated external provider failure"
        ),
    ):
        await service.search(
            query=(
                "latest Python release"
            ),
            max_results=5,
        )