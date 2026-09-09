import re
from urllib.parse import (
    parse_qsl,
    urlencode,
    urlparse,
    urlunparse,
)

from pydantic import (
    ValidationError,
)

from app.schemas.web import (
    WebSearchResult,
    WebSourceMetadata,
)
from app.web.base import (
    RawWebSearchResult,
)


class WebRankingService:
    """
    Rank web-search results using:

    - provider confidence
    - lexical query relevance
    - content quality
    - source authority
    - query intent

    Authority is deliberately contextual.

    Example:
    - For a factual software-release query, official
      documentation should usually outrank a forum.
    - For a query explicitly asking for Reddit/community
      opinions, community sources should not be unfairly
      penalized.

    The service remains deterministic and does not require
    an additional LLM call.
    """

    TRACKING_PARAMETERS = {
        "fbclid",
        "gclid",
        "mc_cid",
        "mc_eid",
        "ref",
        "source",
    }

    TRACKING_PREFIXES = (
        "utm_",
    )

    #
    # Domains that generally represent strong primary,
    # standards, academic, government, or authoritative
    # technical sources.
    #
    # This list is intentionally general rather than
    # product-query-specific.
    #
    HIGH_AUTHORITY_DOMAINS = {
        "arxiv.org",
        "acm.org",
        "ieee.org",
        "ietf.org",
        "w3.org",
        "nist.gov",
        "who.int",
        "worldbank.org",
        "oecd.org",
    }

    #
    # Well-established technical/reference sources.
    #
    STRONG_REFERENCE_DOMAINS = {
        "developer.mozilla.org",
        "stackoverflow.com",
        "wikipedia.org",
    }

    #
    # Community/social/video platforms.
    #
    # These are not "bad" sources. They simply should not
    # normally outrank a primary source for factual claims.
    #
    COMMUNITY_DOMAINS = {
        "reddit.com",
        "quora.com",
        "stackoverflow.com",
        "stackexchange.com",
    }

    SOCIAL_VIDEO_DOMAINS = {
        "youtube.com",
        "youtu.be",
        "x.com",
        "twitter.com",
        "facebook.com",
        "instagram.com",
        "tiktok.com",
        "linkedin.com",
        "medium.com",
    }

    #
    # Common official-documentation / primary-source
    # path signals.
    #
    OFFICIAL_PATH_SIGNALS = (
        "/docs",
        "/documentation",
        "/developers",
        "/developer",
        "/reference",
        "/api",
        "/releases",
        "/release",
        "/changelog",
        "/news",
        "/blog",
        "/press",
        "/security",
        "/standards",
        "/spec",
        "/specification",
    )

    PRIMARY_TITLE_SIGNALS = (
        "official",
        "documentation",
        "docs",
        "release notes",
        "release",
        "changelog",
        "announcement",
        "security advisory",
        "specification",
        "standard",
        "developer documentation",
        "api reference",
    )

    COMMUNITY_INTENT_PATTERNS = (
        r"\breddit\b",
        r"\bcommunity\b",
        r"\bforum\b",
        r"\bforums\b",
        r"\buser\s+opinions?\b",
        r"\bpeople\s+think\b",
        r"\bwhat\s+people\s+say\b",
        r"\breviews?\b",
        r"\bexperiences?\b",
        r"\bdiscussion\b",
        r"\bdiscussions\b",
        r"\bsocial\s+media\b",
        r"\byoutube\b",
        r"\bpublic\s+reaction\b",
        r"\busers?\s+kya\s+bol\b",
        r"\blog\s+kya\s+bol\b",
    )

    #
    # Queries with these signals generally benefit more
    # from primary/official evidence.
    #
    PRIMARY_SOURCE_INTENT_PATTERNS = (
        r"\blatest\b",
        r"\bcurrent\b",
        r"\bofficial\b",
        r"\brelease\b",
        r"\bversion\b",
        r"\bchangelog\b",
        r"\bannouncement\b",
        r"\bsecurity\s+advisory\b",
        r"\bdocumentation\b",
        r"\bdocs\b",
        r"\bapi\b",
        r"\bspecification\b",
        r"\bstandard\b",
        r"\bpolicy\b",
        r"\bprice\b",
        r"\bpricing\b",
    )

    @staticmethod
    def _clamp(
        value: float,
    ) -> float:
        return max(
            0.0,
            min(
                value,
                1.0,
            ),
        )

    @staticmethod
    def _normalize_text(
        value: str,
    ) -> str:
        return re.sub(
            r"\s+",
            " ",
            value,
        ).strip().lower()

    @staticmethod
    def _tokenize(
        value: str,
    ) -> set[str]:
        tokens = re.findall(
            r"[a-zA-Z0-9]+",
            value.lower(),
        )

        return {
            token
            for token in tokens
            if len(token) >= 2
        }

    @staticmethod
    def _domain_from_url(
        url: str,
    ) -> str:
        parsed = urlparse(
            url
        )

        hostname = (
            parsed.hostname
            or ""
        ).lower().rstrip(".")

        if hostname.startswith(
            "www."
        ):
            hostname = hostname[4:]

        return hostname

    @staticmethod
    def _domain_matches(
        domain: str,
        candidate: str,
    ) -> bool:
        """
        Match both the root domain and its subdomains.

        Example:
        docs.python.org matches python.org.
        """

        domain = (
            domain
            .lower()
            .rstrip(".")
        )

        candidate = (
            candidate
            .lower()
            .rstrip(".")
        )

        return (
            domain == candidate
            or domain.endswith(
                f".{candidate}"
            )
        )

    @classmethod
    def _matches_any_domain(
        cls,
        domain: str,
        candidates: set[str],
    ) -> bool:
        return any(
            cls._domain_matches(
                domain,
                candidate,
            )
            for candidate
            in candidates
        )

    @classmethod
    def _canonicalize_url(
        cls,
        url: str,
    ) -> str:
        parsed = urlparse(
            url
        )

        filtered_query = []

        for key, value in parse_qsl(
            parsed.query,
            keep_blank_values=True,
        ):
            lower_key = (
                key.lower()
            )

            if (
                lower_key
                in cls.TRACKING_PARAMETERS
            ):
                continue

            if any(
                lower_key.startswith(
                    prefix
                )
                for prefix
                in cls.TRACKING_PREFIXES
            ):
                continue

            filtered_query.append(
                (
                    key,
                    value,
                )
            )

        clean_path = (
            parsed.path
            or "/"
        )

        if (
            clean_path != "/"
            and clean_path.endswith("/")
        ):
            clean_path = (
                clean_path[:-1]
            )

        return urlunparse(
            (
                parsed.scheme.lower(),
                parsed.netloc.lower(),
                clean_path,
                "",
                urlencode(
                    filtered_query,
                    doseq=True,
                ),
                "",
            )
        )

    @classmethod
    def _lexical_relevance(
        cls,
        *,
        query: str,
        title: str,
        content: str,
    ) -> float:
        query_tokens = (
            cls._tokenize(
                query
            )
        )

        if not query_tokens:
            return 0.0

        title_tokens = (
            cls._tokenize(
                title
            )
        )

        content_tokens = (
            cls._tokenize(
                content
            )
        )

        title_matches = len(
            query_tokens
            & title_tokens
        )

        content_matches = len(
            query_tokens
            & content_tokens
        )

        title_ratio = (
            title_matches
            / len(query_tokens)
        )

        content_ratio = (
            content_matches
            / len(query_tokens)
        )

        score = (
            title_ratio
            * 0.65
            + content_ratio
            * 0.35
        )

        return cls._clamp(
            score
        )

    @classmethod
    def _content_quality(
        cls,
        content: str,
    ) -> float:
        cleaned = (
            content
            .strip()
        )

        length = len(
            cleaned
        )

        if length <= 0:
            return 0.0

        #
        # Very tiny snippets carry less evidence.
        #
        if length < 80:
            return cls._clamp(
                length / 160
            )

        if length >= 600:
            return 1.0

        return cls._clamp(
            length / 600
        )

    @classmethod
    def _provider_score(
        cls,
        score: float | None,
    ) -> float | None:
        if score is None:
            return None

        return cls._clamp(
            score
        )

    @classmethod
    def _has_community_intent(
        cls,
        query: str,
    ) -> bool:
        normalized = (
            cls._normalize_text(
                query
            )
        )

        return any(
            re.search(
                pattern,
                normalized,
                flags=re.IGNORECASE,
            )
            is not None
            for pattern
            in cls.COMMUNITY_INTENT_PATTERNS
        )

    @classmethod
    def _has_primary_source_intent(
        cls,
        query: str,
    ) -> bool:
        normalized = (
            cls._normalize_text(
                query
            )
        )

        return any(
            re.search(
                pattern,
                normalized,
                flags=re.IGNORECASE,
            )
            is not None
            for pattern
            in cls.PRIMARY_SOURCE_INTENT_PATTERNS
        )

    @classmethod
    def _looks_like_official_source(
        cls,
        *,
        query: str,
        result: RawWebSearchResult,
    ) -> bool:
        """
        Infer whether a result looks like a primary or
        official source without hard-coding one product.

        This is a heuristic, not a proof of ownership.

        We therefore use it as one ranking signal only,
        never as a security or identity guarantee.
        """

        parsed = urlparse(
            result.url
        )

        domain = (
            cls._domain_from_url(
                result.url
            )
        )

        path = (
            parsed.path
            or "/"
        ).lower()

        title = (
            cls._normalize_text(
                result.title
            )
        )

        query_tokens = (
            cls._tokenize(
                query
            )
        )

        domain_tokens = set(
            re.findall(
                r"[a-zA-Z0-9]+",
                domain.lower(),
            )
        )

        title_has_primary_signal = any(
            signal in title
            for signal
            in cls.PRIMARY_TITLE_SIGNALS
        )

        path_has_primary_signal = any(
            signal in path
            for signal
            in cls.OFFICIAL_PATH_SIGNALS
        )

        #
        # If meaningful query tokens appear directly in
        # the domain, that is useful supporting evidence.
        #
        # Example:
        # python -> python.org
        # fastapi -> fastapi.tiangolo.com
        #
        generic_tokens = {
            "latest",
            "current",
            "official",
            "release",
            "version",
            "docs",
            "documentation",
            "api",
            "news",
            "today",
            "update",
            "updates",
            "what",
            "when",
            "where",
            "which",
            "the",
            "and",
            "for",
            "kya",
            "hai",
            "batao",
            "btao",
        }

        meaningful_query_tokens = {
            token
            for token
            in query_tokens
            if token
            not in generic_tokens
            and len(token) >= 3
        }

        domain_query_overlap = bool(
            meaningful_query_tokens
            & domain_tokens
        )

        #
        # A path/title signal alone is too weak because any
        # random blog can create /docs or write "official".
        #
        return (
            domain_query_overlap
            and (
                path_has_primary_signal
                or title_has_primary_signal
            )
        )

    @classmethod
    def _authority_score(
        cls,
        *,
        query: str,
        result: RawWebSearchResult,
    ) -> float:
        """
        Estimate contextual source authority.

        0.0 = very weak for this query
        1.0 = very strong for this query

        Authority is a ranking heuristic only.
        It is NOT used as a trust/security permission.
        """

        domain = (
            cls._domain_from_url(
                result.url
            )
        )

        if not domain:
            return 0.0

        community_intent = (
            cls._has_community_intent(
                query
            )
        )

        primary_intent = (
            cls._has_primary_source_intent(
                query
            )
        )

        is_community = (
            cls._matches_any_domain(
                domain,
                cls.COMMUNITY_DOMAINS,
            )
        )

        is_social_video = (
            cls._matches_any_domain(
                domain,
                cls.SOCIAL_VIDEO_DOMAINS,
            )
        )

        is_high_authority = (
            cls._matches_any_domain(
                domain,
                cls.HIGH_AUTHORITY_DOMAINS,
            )
        )

        is_strong_reference = (
            cls._matches_any_domain(
                domain,
                cls.STRONG_REFERENCE_DOMAINS,
            )
        )

        looks_official = (
            cls._looks_like_official_source(
                query=query,
                result=result,
            )
        )

        #
        # Contextual community queries:
        #
        # "What are Reddit users saying?"
        #
        # Reddit/community content is primary evidence for
        # that specific question.
        #
        if community_intent:
            if is_community:
                return 0.95

            if is_social_video:
                return 0.85

            if looks_official:
                return 0.72

            if is_high_authority:
                return 0.72

            if is_strong_reference:
                return 0.68

            return 0.58

        #
        # Normal factual/current queries.
        #
        if looks_official:
            return 1.0

        if is_high_authority:
            return 0.95

        #
        # Government and education domains are often useful
        # primary/institutional sources.
        #
        if (
            domain.endswith(".gov")
            or ".gov." in domain
        ):
            return 0.94

        if (
            domain.endswith(".edu")
            or ".edu." in domain
            or domain.endswith(".ac.uk")
        ):
            return 0.90

        if is_strong_reference:
            return (
                0.78
                if primary_intent
                else 0.82
            )

        if is_community:
            return (
                0.45
                if primary_intent
                else 0.58
            )

        if is_social_video:
            return (
                0.35
                if primary_intent
                else 0.50
            )

        #
        # Unknown public source.
        #
        return 0.62

    @classmethod
    def _calculate_relevance(
        cls,
        *,
        query: str,
        result: RawWebSearchResult,
    ) -> float:
        lexical_score = (
            cls._lexical_relevance(
                query=query,
                title=result.title,
                content=result.content,
            )
        )

        quality_score = (
            cls._content_quality(
                result.content
            )
        )

        provider_score = (
            cls._provider_score(
                result.provider_score
            )
        )

        authority_score = (
            cls._authority_score(
                query=query,
                result=result,
            )
        )

        community_intent = (
            cls._has_community_intent(
                query
            )
        )

        #
        # Provider relevance remains the strongest signal,
        # but authority now has enough weight to promote
        # primary sources over weak aggregators when their
        # query relevance is comparable.
        #
        if provider_score is None:
            if community_intent:
                combined = (
                    lexical_score
                    * 0.55
                    + authority_score
                    * 0.30
                    + quality_score
                    * 0.15
                )
            else:
                combined = (
                    lexical_score
                    * 0.50
                    + authority_score
                    * 0.35
                    + quality_score
                    * 0.15
                )

        else:
            if community_intent:
                combined = (
                    provider_score
                    * 0.45
                    + lexical_score
                    * 0.25
                    + authority_score
                    * 0.20
                    + quality_score
                    * 0.10
                )
            else:
                combined = (
                    provider_score
                    * 0.45
                    + lexical_score
                    * 0.25
                    + authority_score
                    * 0.20
                    + quality_score
                    * 0.10
                )

        return round(
            cls._clamp(
                combined
            ),
            6,
        )

    @classmethod
    def _deduplicate(
        cls,
        results: list[
            RawWebSearchResult
        ],
    ) -> list[
        RawWebSearchResult
    ]:
        unique_results: list[
            RawWebSearchResult
        ] = []

        seen_urls: set[str] = set()
        seen_titles: set[str] = set()

        for result in results:
            canonical_url = (
                cls._canonicalize_url(
                    result.url
                )
            )

            normalized_title = (
                cls._normalize_text(
                    result.title
                )
            )

            if (
                canonical_url
                in seen_urls
            ):
                continue

            if (
                normalized_title
                and normalized_title
                in seen_titles
            ):
                continue

            seen_urls.add(
                canonical_url
            )

            if normalized_title:
                seen_titles.add(
                    normalized_title
                )

            unique_results.append(
                result
            )

        return unique_results

    @classmethod
    def rank_results(
        cls,
        *,
        query: str,
        results: list[
            RawWebSearchResult
        ],
        max_results: int,
    ) -> list[
        WebSearchResult
    ]:
        deduplicated = (
            cls._deduplicate(
                results
            )
        )

        scored_results = [
            (
                result,
                cls._calculate_relevance(
                    query=query,
                    result=result,
                ),
                cls._authority_score(
                    query=query,
                    result=result,
                ),
            )
            for result
            in deduplicated
        ]

        scored_results.sort(
            key=lambda item: (
                item[1],
                item[2],
                (
                    item[0]
                    .provider_score
                    if item[0]
                    .provider_score
                    is not None
                    else -1.0
                ),
            ),
            reverse=True,
        )

        #
        # Important:
        #
        # Validate first and assign citation IDs second.
        #
        # The previous implementation enumerated before
        # Pydantic validation. If an invalid result was
        # skipped, citations could become:
        #
        # W1, W3, W4
        #
        # instead of:
        #
        # W1, W2, W3
        #
        valid_candidates: list[
            tuple[
                RawWebSearchResult,
                float,
                str,
            ]
        ] = []

        for (
            result,
            relevance_score,
            _authority_score,
        ) in scored_results:
            domain = (
                cls._domain_from_url(
                    result.url
                )
            )

            if not domain:
                continue

            #
            # Validate URL/result structure before final
            # citation numbering.
            #
            try:
                temporary_result = (
                    WebSearchResult(
                        title=result.title,
                        url=result.url,
                        content=(
                            result.content
                        ),
                        source=(
                            WebSourceMetadata(
                                citation_id="W1",
                                domain=domain,
                                rank=1,
                                provider_score=(
                                    cls._provider_score(
                                        result.provider_score
                                    )
                                ),
                                relevance_score=(
                                    relevance_score
                                ),
                            )
                        ),
                    )
                )

            except ValidationError:
                continue

            valid_candidates.append(
                (
                    result,
                    relevance_score,
                    domain,
                )
            )

            if (
                len(valid_candidates)
                >= max_results
            ):
                break

        ranked_results: list[
            WebSearchResult
        ] = []

        for index, (
            result,
            relevance_score,
            domain,
        ) in enumerate(
            valid_candidates,
            start=1,
        ):
            ranked_results.append(
                WebSearchResult(
                    title=result.title,
                    url=result.url,
                    content=(
                        result.content
                    ),
                    source=(
                        WebSourceMetadata(
                            citation_id=(
                                f"W{index}"
                            ),
                            domain=domain,
                            rank=index,
                            provider_score=(
                                cls._provider_score(
                                    result.provider_score
                                )
                            ),
                            relevance_score=(
                                relevance_score
                            ),
                        )
                    ),
                )
            )

        return ranked_results


web_ranking_service = (
    WebRankingService()
)