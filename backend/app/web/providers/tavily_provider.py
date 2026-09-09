import os
from pathlib import Path

import httpx
from dotenv import (
    load_dotenv,
)

from app.services.web_security_service import (
    web_security_service,
)
from app.web.base import (
    RawWebSearchResult,
    WebSearchProvider,
)


BACKEND_DIR = (
    Path(__file__)
    .resolve()
    .parents[3]
)

ENV_FILE = (
    BACKEND_DIR
    / ".env"
)

load_dotenv(
    dotenv_path=ENV_FILE,
    override=False,
)


class TavilyWebSearchProvider(
    WebSearchProvider
):
    provider_name = "tavily"

    API_URL = (
        "https://api.tavily.com/search"
    )

    REQUEST_TIMEOUT_SECONDS = 15.0


    def _require_api_key(
        self,
    ) -> str:
        api_key = (
            os.getenv(
                "TAVILY_API_KEY",
                "",
            )
            .strip()
        )

        if not api_key:
            raise RuntimeError(
                "TAVILY_API_KEY is not configured."
            )

        return api_key


    async def search(
        self,
        *,
        query: str,
        max_results: int,
    ) -> list[
        RawWebSearchResult
    ]:
        api_key = (
            self._require_api_key()
        )

        safe_query = (
            web_security_service
            .sanitize_query(
                query
            )
        )

        payload = {
            "api_key":
                api_key,

            "query":
                safe_query,

            "search_depth":
                "basic",

            "max_results":
                max_results,

            "include_answer":
                False,

            "include_raw_content":
                False,

            "include_images":
                False,
        }

        timeout = httpx.Timeout(
            self.REQUEST_TIMEOUT_SECONDS
        )

        try:
            async with (
                httpx.AsyncClient(
                    timeout=timeout,
                    follow_redirects=False,
                )
            ) as client:
                response = (
                    await client.post(
                        self.API_URL,
                        json=payload,
                        headers={
                            "Accept":
                                "application/json",

                            "Content-Type":
                                "application/json",
                        },
                    )
                )

        except httpx.TimeoutException as exc:
            raise RuntimeError(
                "The web search provider "
                "timed out."
            ) from exc

        except httpx.RequestError as exc:
            raise RuntimeError(
                "Unable to connect to "
                "the web search provider."
            ) from exc


        if (
            response.status_code
            == 401
        ):
            raise RuntimeError(
                "Web search authentication failed. "
                "Check TAVILY_API_KEY."
            )


        if (
            response.status_code
            == 403
        ):
            raise RuntimeError(
                "Web search access was denied "
                "by the provider."
            )


        if (
            response.status_code
            == 429
        ):
            raise RuntimeError(
                "Web search quota or "
                "rate limit was reached."
            )


        if (
            response.status_code
            >= 500
        ):
            raise RuntimeError(
                "The web search provider "
                "is temporarily unavailable."
            )


        if not response.is_success:
            raise RuntimeError(
                "The web search request failed "
                f"with status "
                f"{response.status_code}."
            )


        try:
            data = response.json()

        except ValueError as exc:
            raise RuntimeError(
                "The web search provider "
                "returned invalid JSON."
            ) from exc


        raw_results = data.get(
            "results",
            [],
        )


        if not isinstance(
            raw_results,
            list,
        ):
            raise RuntimeError(
                "The web search provider "
                "returned an invalid result format."
            )


        results: list[
            RawWebSearchResult
        ] = []


        for item in raw_results:
            if not isinstance(
                item,
                dict,
            ):
                continue


            title = str(
                item.get(
                    "title",
                    "",
                )
            ).strip()


            url = str(
                item.get(
                    "url",
                    "",
                )
            ).strip()


            content = str(
                item.get(
                    "content",
                    "",
                )
            ).strip()


            score_value = (
                item.get(
                    "score"
                )
            )


            if (
                not title
                or not url
                or not content
            ):
                continue


            if not (
                web_security_service
                .is_safe_public_url(
                    url
                )
            ):
                continue


            safe_title = (
                web_security_service
                .sanitize_content(
                    title
                )
            )[:500]


            safe_content = (
                web_security_service
                .sanitize_content(
                    content
                )
            )


            if (
                not safe_title
                or not safe_content
            ):
                continue


            try:
                provider_score = (
                    float(
                        score_value
                    )
                    if score_value
                    is not None
                    else None
                )

            except (
                TypeError,
                ValueError,
            ):
                provider_score = None


            results.append(
                RawWebSearchResult(
                    title=safe_title,
                    url=url,
                    content=safe_content,
                    provider_score=(
                        provider_score
                    ),
                )
            )


        return results[
            :max_results
        ]