from app.schemas.web import (
    WebSearchResponse,
)
from app.services.web_ranking_service import (
    web_ranking_service,
)
from app.services.web_security_service import (
    web_security_service,
)
from app.web.base import (
    WebSearchProvider,
)
from app.web.providers.tavily_provider import (
    TavilyWebSearchProvider,
)


class WebSearchService:
    def __init__(
        self,
        provider: (
            WebSearchProvider
            | None
        ) = None,
    ) -> None:
        self.provider = (
            provider
            or TavilyWebSearchProvider()
        )


    async def search(
        self,
        *,
        query: str,
        max_results: int = 5,
    ) -> WebSearchResponse:
        safe_query = (
            web_security_service
            .sanitize_query(
                query
            )
        )


        bounded_max_results = max(
            1,
            min(
                max_results,
                10,
            ),
        )


        raw_results = (
            await self.provider.search(
                query=safe_query,
                max_results=(
                    bounded_max_results
                ),
            )
        )


        ranked_results = (
            web_ranking_service
            .rank_results(
                query=safe_query,
                results=raw_results,
                max_results=(
                    bounded_max_results
                ),
            )
        )


        return WebSearchResponse(
            query=safe_query,
            provider=(
                self.provider
                .provider_name
            ),
            results=ranked_results,
        )


web_search_service = (
    WebSearchService()
)