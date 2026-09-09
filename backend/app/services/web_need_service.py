import re
from datetime import (
    datetime,
    timezone,
)

from app.schemas.web_routing import (
    WebNeedDecisionResponse,
)
from app.services.web_security_service import (
    web_security_service,
)


class WebNeedService:
    """
    Deterministic first-stage router for deciding
    whether a user query requires live web access.

    Important:
    - It does not perform the search.
    - It does not call the LLM.
    - It does not access memory or documents.
    - It only classifies the current message.
    """

    EXPLICIT_WEB_PATTERNS = (
        r"\bsearch\s+(the\s+)?web\b",
        r"\bsearch\s+(the\s+)?internet\b",
        r"\blook\s+(it\s+)?up\s+online\b",
        r"\blook\s+this\s+up\b",
        r"\bcheck\s+online\b",
        r"\bcheck\s+the\s+web\b",
        r"\bgoogle\s+it\b",
        r"\bweb\s+se\s+search\b",
        r"\binternet\s+se\s+search\b",
        r"\bonline\s+check\s+karo\b",
        r"\bweb\s+pe\s+check\b",
        r"\binternet\s+pe\s+check\b",
        r"\bsearch\s+karke\s+batao\b",
        r"\bcheck\s+karke\s+batao\b",
    )

    EXPLICIT_NO_WEB_PATTERNS = (
        r"\bdo\s+not\s+search\s+(the\s+)?web\b",
        r"\bdon'?t\s+search\s+(the\s+)?web\b",
        r"\bwithout\s+(using\s+)?the\s+web\b",
        r"\bwithout\s+web\s+search\b",
        r"\bno\s+web\s+search\b",
        r"\boffline\s+answer\b",
        r"\bweb\s+use\s+mat\s+karo\b",
        r"\binternet\s+use\s+mat\s+karo\b",
        r"\bsearch\s+mat\s+karo\b",
        r"\bonline\s+check\s+mat\s+karo\b",
    )

    CURRENT_INFORMATION_PATTERNS = (
        r"\blatest\b",
        r"\bcurrent\b",
        r"\bcurrently\b",
        r"\bright\s+now\b",
        r"\btoday\b",
        r"\btonight\b",
        r"\bthis\s+week\b",
        r"\bthis\s+month\b",
        r"\brecent\b",
        r"\brecently\b",
        r"\bnewest\b",
        r"\bmost\s+recent\b",
        r"\bup[\s-]?to[\s-]?date\b",
        r"\bas\s+of\s+today\b",
        r"\babhi\b",
        r"\baaj\b",
        r"\bhaal\s+hi\b",
        r"\bnaya\s+update\b",
        r"\blatest\s+update\b",
    )

    VOLATILE_TOPIC_PATTERNS = (
        r"\bnews\b",
        r"\bweather\b",
        r"\btemperature\b",
        r"\bforecast\b",
        r"\bstock\b",
        r"\bshare\s+price\b",
        r"\bmarket\s+price\b",
        r"\bcrypto\b",
        r"\bbitcoin\b",
        r"\bethereum\b",
        r"\bexchange\s+rate\b",
        r"\bcurrency\s+rate\b",
        r"\bsports\s+score\b",
        r"\blive\s+score\b",
        r"\bmatch\s+score\b",
        r"\bstandings\b",
        r"\bflight\s+status\b",
        r"\btrain\s+status\b",
        r"\btraffic\b",
        r"\bavailability\b",
        r"\bprice\s+today\b",
        r"\bjob\s+opening\b",
        r"\bjob\s+vacancy\b",
        r"\bhiring\b",
        r"\bcompany\s+opening\b",
        r"\brelease\s+date\b",
        r"\bversion\s+released\b",
    )

    PERSONAL_CONTEXT_PATTERNS = (
        r"\bwhat\s+do\s+i\s+prefer\b",
        r"\bwhat\s+did\s+i\s+prefer\b",
        r"\bwhat\s+did\s+i\s+tell\s+you\b",
        r"\bwhat\s+did\s+i\s+say\b",
        r"\bremember\s+what\s+i\b",
        r"\bmy\s+preference\b",
        r"\bmy\s+saved\s+memory\b",
        r"\bmeri\s+preference\b",
        r"\bmaine\s+tumhe\s+kya\s+bataya\b",
        r"\bmaine\s+kya\s+bola\b",
        r"\byaad\s+hai\b",
        r"\bmeri\s+memory\b",
    )

    DOCUMENT_CONTEXT_PATTERNS = (
        r"\bthis\s+document\b",
        r"\bthe\s+document\b",
        r"\bthis\s+pdf\b",
        r"\bthe\s+pdf\b",
        r"\bthis\s+file\b",
        r"\bthe\s+file\b",
        r"\buploaded\s+file\b",
        r"\buploaded\s+document\b",
        r"\battachment\b",
        r"\battached\s+file\b",
        r"\battached\s+document\b",
        r"\biss\s+pdf\b",
        r"\bis\s+pdf\b",
        r"\biss\s+file\b",
        r"\bis\s+file\b",
        r"\bupload\s+ki\s+hui\b",
    )

    STABLE_KNOWLEDGE_PATTERNS = (
        r"^\s*what\s+is\b",
        r"^\s*what\s+are\b",
        r"^\s*define\b",
        r"^\s*explain\b",
        r"^\s*how\s+does\b",
        r"^\s*how\s+do\b",
        r"^\s*why\s+does\b",
        r"^\s*difference\s+between\b",
        r"^\s*compare\b",
        r"^\s*write\s+(a\s+)?program\b",
        r"^\s*create\s+(a\s+)?function\b",
        r"^\s*implement\b",
        r"^\s*recursion\b",
        r"^\s*explain\s+kar\b",
        r"^\s*kya\s+hai\b",
        r"^\s*kya\s+hota\s+hai\b",
        r"^\s*samjhao\b",
    )

    FRESHNESS_WORDS = {
        "latest",
        "current",
        "currently",
        "today",
        "recent",
        "recently",
        "newest",
        "update",
        "updated",
        "live",
        "abhi",
        "aaj",
    }


    @staticmethod
    def _matches(
        text: str,
        patterns: tuple[str, ...],
    ) -> bool:
        return any(
            re.search(
                pattern,
                text,
                flags=re.IGNORECASE,
            )
            for pattern in patterns
        )


    @staticmethod
    def _normalize(
        message: str,
    ) -> str:
        return re.sub(
            r"\s+",
            " ",
            message,
        ).strip()


    @classmethod
    def _contains_recent_year(
        cls,
        message: str,
    ) -> bool:
        current_year = (
            datetime.now(
                timezone.utc
            ).year
        )

        years = re.findall(
            r"\b(20\d{2})\b",
            message,
        )

        if not years:
            return False

        parsed_years = {
            int(year)
            for year in years
        }

        return any(
            year >= current_year - 1
            for year in parsed_years
        )


    @classmethod
    def _contains_freshness_word(
        cls,
        message: str,
    ) -> bool:
        tokens = set(
            re.findall(
                r"[a-zA-Z0-9]+",
                message.lower(),
            )
        )

        return bool(
            tokens
            & cls.FRESHNESS_WORDS
        )


    @classmethod
    def decide(
        cls,
        *,
        message: str,
        web_allowed: bool = True,
    ) -> WebNeedDecisionResponse:
        normalized = (
            cls._normalize(
                message
            )
        )

        if not normalized:
            return WebNeedDecisionResponse(
                needs_web=False,
                confidence=1.0,
                reason="stable_knowledge",
                explanation=(
                    "The message is empty after normalization."
                ),
                normalized_query=None,
            )


        if not web_allowed:
            return WebNeedDecisionResponse(
                needs_web=False,
                confidence=1.0,
                reason="web_disabled",
                explanation=(
                    "Web access is disabled for this request."
                ),
                normalized_query=None,
            )


        if cls._matches(
            normalized,
            cls.EXPLICIT_NO_WEB_PATTERNS,
        ):
            return WebNeedDecisionResponse(
                needs_web=False,
                confidence=1.0,
                reason="explicit_no_web_request",
                explanation=(
                    "The user explicitly requested "
                    "that web search not be used."
                ),
                normalized_query=None,
            )


        if cls._matches(
            normalized,
            cls.EXPLICIT_WEB_PATTERNS,
        ):
            return WebNeedDecisionResponse(
                needs_web=True,
                confidence=1.0,
                reason="explicit_web_request",
                explanation=(
                    "The user explicitly requested "
                    "web or internet lookup."
                ),
                normalized_query=normalized,
            )


        if cls._matches(
            normalized,
            cls.PERSONAL_CONTEXT_PATTERNS,
        ):
            return WebNeedDecisionResponse(
                needs_web=False,
                confidence=0.98,
                reason="personal_context",
                explanation=(
                    "The request appears to depend "
                    "on the user's saved personal context "
                    "or memory rather than the public web."
                ),
                normalized_query=None,
            )


        if cls._matches(
            normalized,
            cls.DOCUMENT_CONTEXT_PATTERNS,
        ):
            return WebNeedDecisionResponse(
                needs_web=False,
                confidence=0.97,
                reason="document_context",
                explanation=(
                    "The request appears to depend "
                    "on an uploaded or attached document."
                ),
                normalized_query=None,
            )


        if cls._matches(
            normalized,
            cls.CURRENT_INFORMATION_PATTERNS,
        ):
            return WebNeedDecisionResponse(
                needs_web=True,
                confidence=0.97,
                reason="current_information",
                explanation=(
                    "The query contains freshness or "
                    "current-information language."
                ),
                normalized_query=normalized,
            )


        if cls._matches(
            normalized,
            cls.VOLATILE_TOPIC_PATTERNS,
        ):
            return WebNeedDecisionResponse(
                needs_web=True,
                confidence=0.95,
                reason="volatile_information",
                explanation=(
                    "The query concerns information "
                    "that can change frequently."
                ),
                normalized_query=normalized,
            )


        if (
            cls._contains_recent_year(
                normalized
            )
            and cls._contains_freshness_word(
                normalized
            )
        ):
            return WebNeedDecisionResponse(
                needs_web=True,
                confidence=0.93,
                reason="recent_year_context",
                explanation=(
                    "The query combines a recent year "
                    "with freshness-related wording."
                ),
                normalized_query=normalized,
            )


        if cls._matches(
            normalized,
            cls.STABLE_KNOWLEDGE_PATTERNS,
        ):
            return WebNeedDecisionResponse(
                needs_web=False,
                confidence=0.90,
                reason="stable_knowledge",
                explanation=(
                    "The query appears to ask for "
                    "stable conceptual knowledge."
                ),
                normalized_query=None,
            )


        return WebNeedDecisionResponse(
            needs_web=False,
            confidence=0.60,
            reason="ambiguous",
            explanation=(
                "The query does not clearly require "
                "live web information. The conservative "
                "default is to avoid unnecessary web use."
            ),
            normalized_query=None,
        )


web_need_service = (
    WebNeedService()
)