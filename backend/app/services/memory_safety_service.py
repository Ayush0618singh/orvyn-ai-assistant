import re

from app.schemas.memory_candidate import (
    MemorySafetyResult,
)


class MemorySafetyService:
    """
    Safety layer for automatic long-term memory.

    This service prevents obviously sensitive or secret information
    from being automatically stored as persistent memory.

    Important:
    Explicit user-requested memory and automatic memory are different
    workflows. This service is primarily intended for automatic
    extraction.
    """

    _SENSITIVE_PATTERNS: tuple[
        tuple[str, str, re.Pattern[str]],
        ...
    ] = (
        (
            "password",
            (
                "Passwords must never be "
                "automatically stored."
            ),
            re.compile(
                r"""
                \b
                (
                    password
                    |
                    passwd
                    |
                    passcode
                    |
                    pwd
                )
                \b
                """,
                re.IGNORECASE
                | re.VERBOSE,
            ),
        ),
        (
            "otp",
            (
                "One-time passwords must never "
                "be automatically stored."
            ),
            re.compile(
                r"""
                \b
                (
                    otp
                    |
                    one[\s-]*time[\s-]*password
                    |
                    verification[\s-]*code
                )
                \b
                """,
                re.IGNORECASE
                | re.VERBOSE,
            ),
        ),
        (
            "api_key",
            (
                "API keys and application secrets "
                "must never be automatically stored."
            ),
            re.compile(
                r"""
                \b
                (
                    api[\s_-]*key
                    |
                    api[\s_-]*secret
                    |
                    client[\s_-]*secret
                    |
                    secret[\s_-]*key
                )
                \b
                """,
                re.IGNORECASE
                | re.VERBOSE,
            ),
        ),
        (
            "access_token",
            (
                "Authentication tokens must never "
                "be automatically stored."
            ),
            re.compile(
                r"""
                \b
                (
                    access[\s_-]*token
                    |
                    refresh[\s_-]*token
                    |
                    bearer[\s_-]*token
                    |
                    auth[\s_-]*token
                    |
                    jwt[\s_-]*token
                )
                \b
                """,
                re.IGNORECASE
                | re.VERBOSE,
            ),
        ),
        (
            "private_key",
            (
                "Private keys must never be "
                "automatically stored."
            ),
            re.compile(
                r"""
                (
                    -----BEGIN
                    [\sA-Z]*
                    PRIVATE\sKEY-----
                )
                |
                \bprivate[\s_-]*key\b
                """,
                re.IGNORECASE
                | re.VERBOSE,
            ),
        ),
        (
            "payment_card",
            (
                "Payment card information must "
                "never be automatically stored."
            ),
            re.compile(
                r"""
                \b
                (
                    credit[\s-]*card
                    |
                    debit[\s-]*card
                    |
                    card[\s-]*number
                    |
                    cvv
                    |
                    cvc
                    |
                    expiry[\s-]*date
                )
                \b
                """,
                re.IGNORECASE
                | re.VERBOSE,
            ),
        ),
        (
            "banking_secret",
            (
                "Sensitive banking credentials "
                "must never be automatically stored."
            ),
            re.compile(
                r"""
                \b
                (
                    atm[\s-]*pin
                    |
                    upi[\s-]*pin
                    |
                    transaction[\s-]*pin
                    |
                    netbanking[\s-]*password
                )
                \b
                """,
                re.IGNORECASE
                | re.VERBOSE,
            ),
        ),
    )

    _SECRET_VALUE_PATTERNS: tuple[
        tuple[str, str, re.Pattern[str]],
        ...
    ] = (
        (
            "openai_key",
            (
                "Possible API secret detected."
            ),
            re.compile(
                r"\bsk-[A-Za-z0-9_-]{16,}\b"
            ),
        ),
        (
            "google_api_key",
            (
                "Possible Google API key detected."
            ),
            re.compile(
                r"\bAIza[A-Za-z0-9_-]{20,}\b"
            ),
        ),
        (
            "github_token",
            (
                "Possible GitHub token detected."
            ),
            re.compile(
                r"""
                \b
                (
                    ghp_
                    |
                    gho_
                    |
                    ghu_
                    |
                    ghs_
                    |
                    github_pat_
                )
                [A-Za-z0-9_]{10,}
                \b
                """,
                re.VERBOSE,
            ),
        ),
        (
            "jwt",
            (
                "Possible JWT/authentication token "
                "detected."
            ),
            re.compile(
                r"""
                \b
                eyJ
                [A-Za-z0-9_-]+
                \.
                [A-Za-z0-9_-]+
                \.
                [A-Za-z0-9_-]+
                \b
                """,
                re.VERBOSE,
            ),
        ),
        (
            "private_key_block",
            (
                "Private key material detected."
            ),
            re.compile(
                r"""
                -----BEGIN
                [\sA-Z]*
                PRIVATE\sKEY-----
                """,
                re.IGNORECASE
                | re.VERBOSE,
            ),
        ),
    )

    _HIGHLY_TRANSIENT_PATTERNS: tuple[
        re.Pattern[str],
        ...
    ] = (
        re.compile(
            r"\bmy otp is\b",
            re.IGNORECASE,
        ),
        re.compile(
            r"\bthe otp is\b",
            re.IGNORECASE,
        ),
        re.compile(
            r"\bverification code is\b",
            re.IGNORECASE,
        ),
    )

    def check(
        self,
        text: str,
    ) -> MemorySafetyResult:
        cleaned_text = (
            text.strip()
        )

        if not cleaned_text:
            return MemorySafetyResult(
                allowed=False,
                reason=(
                    "Empty content cannot be "
                    "stored as memory."
                ),
                category="empty",
            )

        for (
            category,
            reason,
            pattern,
        ) in self._SECRET_VALUE_PATTERNS:
            if pattern.search(
                cleaned_text
            ):
                return (
                    MemorySafetyResult(
                        allowed=False,
                        reason=reason,
                        category=category,
                    )
                )

        for (
            category,
            reason,
            pattern,
        ) in self._SENSITIVE_PATTERNS:
            if pattern.search(
                cleaned_text
            ):
                return (
                    MemorySafetyResult(
                        allowed=False,
                        reason=reason,
                        category=category,
                    )
                )

        for pattern in (
            self._HIGHLY_TRANSIENT_PATTERNS
        ):
            if pattern.search(
                cleaned_text
            ):
                return (
                    MemorySafetyResult(
                        allowed=False,
                        reason=(
                            "Temporary authentication "
                            "information should not be "
                            "stored as long-term memory."
                        ),
                        category=(
                            "temporary_secret"
                        ),
                    )
                )

        return MemorySafetyResult(
            allowed=True,
            reason=(
                "No blocked sensitive-data "
                "pattern was detected."
            ),
            category=None,
        )


memory_safety_service = (
    MemorySafetyService()
)