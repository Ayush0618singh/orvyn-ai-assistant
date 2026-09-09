import re
from datetime import (
    datetime,
    timezone,
)


class WebFreshnessService:
    """
    Safety service for questions that require
    live/current information.

    This is intentionally separate from the normal
    web router.

    The web router decides whether ORVYN should search.

    This service protects ORVYN from presenting stale
    model knowledge as verified current information when:
    - web access is disabled,
    - search fails,
    - search returns no usable results.

    This is a defense-in-depth freshness guard.
    """

    EXPLICIT_WEB_PATTERNS = (
        r"\bsearch\s+(the\s+)?web\b",
        r"\bsearch\s+(the\s+)?internet\b",
        r"\blook\s+(it\s+)?up\s+online\b",
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
        r"\bstocks\b",
        r"\bshare\s+price\b",
        r"\bmarket\s+price\b",

        r"\bcrypto\b",
        r"\bbitcoin\b",
        r"\bethereum\b",

        r"\bexchange\s+rate\b",
        r"\bcurrency\s+rate\b",

        r"\belection\b",
        r"\belections\b",

        r"\bscore\b",
        r"\bmatch\s+result\b",
        r"\bsports\s+result\b",

        r"\bflight\s+status\b",

        r"\btraffic\b",

        r"\bprice\s+today\b",
        r"\bavailability\b",

        r"\bceo\b",
        r"\bpresident\b",
        r"\bprime\s+minister\b",
    )

    RECENT_YEAR_TOPIC_PATTERNS = (
        r"\brelease\b",
        r"\bversion\b",
        r"\bupdate\b",
        r"\bnews\b",
        r"\bannouncement\b",
        r"\blaunch\b",
        r"\bmodel\b",
        r"\bpolicy\b",
        r"\bprice\b",
    )

    HINGLISH_MARKERS = (
        "kya",
        "batao",
        "btao",
        "mujhe",
        "mughe",
        "kaise",
        "kyu",
        "kyun",
        "hai",
        "hain",
        "karo",
        "krna",
        "abhi",
        "aaj",
        "wala",
        "vali",
        "latest kya",
    )

    @staticmethod
    def _normalize(
        message: str,
    ) -> str:
        if not isinstance(
            message,
            str,
        ):
            return ""

        return re.sub(
            r"\s+",
            " ",
            message,
        ).strip().lower()

    @classmethod
    def requires_live_verification(
        cls,
        message: str,
    ) -> bool:
        """
        Return True when the request should not be
        confidently answered as current information
        without successful live verification.
        """

        normalized = cls._normalize(
            message
        )

        if not normalized:
            return False

        patterns = (
            cls.EXPLICIT_WEB_PATTERNS
            + cls.CURRENT_INFORMATION_PATTERNS
            + cls.VOLATILE_TOPIC_PATTERNS
        )

        if any(
            re.search(
                pattern,
                normalized,
                flags=re.IGNORECASE,
            )
            for pattern
            in patterns
        ):
            return True

        #
        # Recent-year freshness guard
        #
        # Example:
        # "Python 2026 release"
        # "Gemini 2026 model"
        #
        current_year = (
            datetime.now(
                timezone.utc
            ).year
        )

        years = {
            int(year)
            for year
            in re.findall(
                r"\b(20\d{2})\b",
                normalized,
            )
        }

        contains_recent_year = any(
            year
            >= current_year - 1
            for year
            in years
        )

        if contains_recent_year:
            if any(
                re.search(
                    pattern,
                    normalized,
                    flags=re.IGNORECASE,
                )
                for pattern
                in cls.RECENT_YEAR_TOPIC_PATTERNS
            ):
                return True

        return False

    @classmethod
    def _response_style(
        cls,
        message: str,
    ) -> str:
        """
        Lightweight deterministic language selection
        for guard responses.

        We deliberately do not call the LLM here because
        the guard exists specifically to prevent an
        unverified LLM answer.
        """

        if re.search(
            r"[\u0900-\u097F]",
            message or "",
        ):
            return "hindi"

        normalized = cls._normalize(
            message
        )

        if any(
            marker in normalized
            for marker
            in cls.HINGLISH_MARKERS
        ):
            return "hinglish"

        return "english"

    @classmethod
    def build_unavailable_response(
        cls,
        *,
        message: str,
        reason: str,
    ) -> str:
        """
        Produce a deterministic honest response.

        Supported reasons:
        - web_disabled
        - search_failed
        - no_results
        - unusable_results
        """

        style = cls._response_style(
            message
        )

        if style == "hindi":
            responses = {
                "web_disabled": (
                    "इस प्रश्न का विश्वसनीय उत्तर देने के लिए "
                    "वर्तमान या लाइव जानकारी की पुष्टि आवश्यक है, "
                    "लेकिन वेब एक्सेस अभी बंद है। मैं बिना पुष्टि "
                    "के नवीनतम जानकारी का अनुमान नहीं लगाऊँगा। "
                    "वेब एक्सेस चालू करके दोबारा पूछें।"
                ),

                "search_failed": (
                    "इस प्रश्न के लिए लाइव वेब जानकारी की पुष्टि "
                    "आवश्यक है, लेकिन वेब खोज अभी सफल नहीं हो पाई। "
                    "मैं बिना पुष्टि के नवीनतम जानकारी का अनुमान "
                    "नहीं लगाऊँगा। कृपया थोड़ी देर बाद दोबारा प्रयास करें।"
                ),

                "no_results": (
                    "वेब खोज की गई, लेकिन इस प्रश्न के लिए पर्याप्त "
                    "विश्वसनीय वर्तमान स्रोत नहीं मिले। इसलिए मैं "
                    "नवीनतम जानकारी का अनुमान नहीं लगाऊँगा।"
                ),

                "unusable_results": (
                    "वेब खोज से परिणाम मिले, लेकिन सुरक्षित और उपयोगी "
                    "वर्तमान स्रोत उपलब्ध नहीं थे। इसलिए मैं अपुष्ट "
                    "जानकारी को नवीनतम तथ्य के रूप में प्रस्तुत नहीं करूँगा।"
                ),
            }

        elif style == "hinglish":
            responses = {
                "web_disabled": (
                    "Is question ka reliable answer dene ke liye "
                    "current/live information verify karna zaroori hai, "
                    "lekin Web Access abhi OFF hai. Main bina verification "
                    "ke latest information guess nahi karunga. Web ON karke "
                    "dobara poochho."
                ),

                "search_failed": (
                    "Is question ke liye live web information verify karna "
                    "zaroori hai, lekin web search abhi successfully complete "
                    "nahi ho pa rahi. Main bina verification ke latest/current "
                    "information guess nahi karunga. Thodi der baad retry karo."
                ),

                "no_results": (
                    "Web search run hui, lekin is question ke liye enough "
                    "reliable current sources nahi mile. Isliye main latest "
                    "information guess karke nahi bataunga."
                ),

                "unusable_results": (
                    "Web search se results mile, lekin safe aur usable current "
                    "sources available nahi the. Isliye main unverified "
                    "information ko latest fact ke roop me present nahi karunga."
                ),
            }

        else:
            responses = {
                "web_disabled": (
                    "This question requires current or live information to be "
                    "verified, but web access is disabled. I won't guess or "
                    "present unverified model knowledge as the latest information. "
                    "Enable web access and ask again."
                ),

                "search_failed": (
                    "This question requires live web verification, but the web "
                    "search could not be completed successfully right now. "
                    "I won't guess or present unverified information as current. "
                    "Please try again shortly."
                ),

                "no_results": (
                    "The web search completed, but it did not return enough "
                    "reliable current sources for this question. I won't guess "
                    "the latest information."
                ),

                "unusable_results": (
                    "The web search returned results, but no safe and usable "
                    "current sources were available. I won't present unverified "
                    "information as a current fact."
                ),
            }

        return responses.get(
            reason,
            responses[
                "search_failed"
            ],
        )


web_freshness_service = (
    WebFreshnessService()
)