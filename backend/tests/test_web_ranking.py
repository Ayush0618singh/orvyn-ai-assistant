from app.services.web_ranking_service import (
    web_ranking_service,
)
from app.web.base import (
    RawWebSearchResult,
)


def _result(
    *,
    title: str,
    url: str,
    content: str,
    score: float = 0.80,
) -> RawWebSearchResult:
    return RawWebSearchResult(
        title=title,
        url=url,
        content=content,
        provider_score=score,
    )


def test_official_source_beats_video_for_release_query():
    query = (
        "latest Python release"
    )

    results = [
        _result(
            title=(
                "Latest Python Release Video"
            ),
            url=(
                "https://youtube.com/"
                "watch?v=test"
            ),
            content=(
                "Latest Python release "
                "information and discussion. "
            )
            * 30,
            score=0.82,
        ),
        _result(
            title=(
                "Python Release Notes"
            ),
            url=(
                "https://docs.python.org/"
                "3/whatsnew/"
            ),
            content=(
                "Official Python "
                "documentation release notes "
                "for the latest version. "
            )
            * 30,
            score=0.80,
        ),
    ]

    ranked = (
        web_ranking_service
        .rank_results(
            query=query,
            results=results,
            max_results=5,
        )
    )

    assert len(ranked) == 2

    assert (
        ranked[0]
        .source
        .domain
        == "docs.python.org"
    )

    assert (
        ranked[0]
        .source
        .citation_id
        == "W1"
    )


def test_community_source_is_supported_for_community_query():
    query = (
        "What are Reddit users saying "
        "about the latest Python release?"
    )

    reddit = _result(
        title=(
            "Reddit Python Discussion"
        ),
        url=(
            "https://reddit.com/"
            "r/Python/comments/test"
        ),
        content=(
            "Python users discuss their "
            "experience with the release. "
        )
        * 30,
    )

    official = _result(
        title=(
            "Python Release Notes"
        ),
        url=(
            "https://docs.python.org/"
            "3/whatsnew/"
        ),
        content=(
            "Official Python "
            "documentation. "
        )
        * 30,
    )

    reddit_authority = (
        web_ranking_service
        ._authority_score(
            query=query,
            result=reddit,
        )
    )

    official_authority = (
        web_ranking_service
        ._authority_score(
            query=query,
            result=official,
        )
    )

    assert (
        reddit_authority
        > official_authority
    )


def test_duplicate_urls_are_removed():
    query = (
        "latest Python release"
    )

    results = [
        _result(
            title=(
                "Python Release Notes"
            ),
            url=(
                "https://python.org/"
                "downloads/?utm_source=test"
            ),
            content=(
                "Official Python release."
            )
            * 30,
        ),
        _result(
            title=(
                "Python Downloads"
            ),
            url=(
                "https://python.org/"
                "downloads/"
            ),
            content=(
                "Python downloads."
            )
            * 30,
        ),
    ]

    ranked = (
        web_ranking_service
        .rank_results(
            query=query,
            results=results,
            max_results=5,
        )
    )

    assert len(ranked) == 1


def test_citation_ids_are_contiguous():
    query = (
        "latest Python release"
    )

    results = [
        _result(
            title="Python Docs",
            url=(
                "https://docs.python.org/"
                "3/"
            ),
            content=(
                "Python documentation."
            )
            * 30,
        ),
        _result(
            title="Python Website",
            url=(
                "https://python.org/"
                "downloads/"
            ),
            content=(
                "Python downloads."
            )
            * 30,
        ),
        _result(
            title="Python Reference",
            url=(
                "https://en.wikipedia.org/"
                "wiki/Python_"
                "(programming_language)"
            ),
            content=(
                "Python reference."
            )
            * 30,
        ),
    ]

    ranked = (
        web_ranking_service
        .rank_results(
            query=query,
            results=results,
            max_results=5,
        )
    )

    citation_ids = [
        result.source.citation_id
        for result
        in ranked
    ]

    expected = [
        f"W{index}"
        for index
        in range(
            1,
            len(ranked) + 1,
        )
    ]

    assert (
        citation_ids
        == expected
    )


def test_tracking_parameters_do_not_create_duplicates():
    first = (
        "https://example.com/article"
        "?utm_source=test"
        "&utm_campaign=abc"
    )

    second = (
        "https://example.com/article"
    )

    first_canonical = (
        web_ranking_service
        ._canonicalize_url(
            first
        )
    )

    second_canonical = (
        web_ranking_service
        ._canonicalize_url(
            second
        )
    )

    assert (
        first_canonical
        == second_canonical
    )