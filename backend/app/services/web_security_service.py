import asyncio
import ipaddress
import re
import socket
import unicodedata
from urllib.parse import (
    urljoin,
    urlparse,
)


class WebSecurityService:
    """
    Central security boundary for external web data
    and future outbound web requests.

    Responsibilities:
    - Search-query normalization.
    - Prompt-injection detection/sanitization.
    - URL syntax validation.
    - Private/internal network blocking.
    - IPv4/IPv6 validation.
    - DNS resolution safety checks.
    - Redirect-target validation.

    Important:
    Search-result content remains untrusted even after
    sanitization.

    Also important:
    DNS validation alone is not sufficient for a future
    arbitrary HTTP fetcher. A production fetcher should
    additionally control redirects, connection targets,
    response sizes, content types, timeouts, and network
    egress.
    """

    MAX_QUERY_LENGTH = 1000
    MAX_CONTENT_LENGTH = 4000
    MAX_TITLE_LENGTH = 500

    DNS_RESOLUTION_TIMEOUT_SECONDS = 3.0

    MAX_REDIRECTS = 5

    REMOVED_INSTRUCTION_MARKER = (
        "[REMOVED_UNTRUSTED_INSTRUCTION]"
    )

    ALLOWED_SCHEMES = {
        "http",
        "https",
    }

    BLOCKED_SCHEMES = {
        "file",
        "ftp",
        "data",
        "javascript",
        "mailto",
        "ssh",
        "telnet",
        "gopher",
        "ws",
        "wss",
    }

    BLOCKED_HOSTNAMES = {
        "localhost",
        "localhost.localdomain",
        "ip6-localhost",
        "ip6-loopback",
    }

    BLOCKED_HOST_SUFFIXES = (
        ".localhost",
        ".local",
        ".internal",
        ".intranet",
        ".lan",
        ".home",
        ".home.arpa",
    )

    PROMPT_INJECTION_PATTERNS = (
        # Instruction hierarchy attacks
        r"\bignore\s+(all\s+)?previous\s+instructions?\b",
        r"\bignore\s+(all\s+)?prior\s+instructions?\b",
        r"\bignore\s+(all\s+)?above\s+instructions?\b",
        r"\bdisregard\s+(all\s+)?previous\s+instructions?\b",
        r"\bdisregard\s+(all\s+)?prior\s+instructions?\b",
        r"\bforget\s+(all\s+)?previous\s+instructions?\b",
        r"\boverride\s+(the\s+)?previous\s+instructions?\b",

        # Role manipulation
        r"\byou\s+are\s+now\s+(the\s+)?system\b",
        r"\byou\s+are\s+now\s+(a\s+)?developer\b",
        r"\bact\s+as\s+(the\s+)?system\b",
        r"\bact\s+as\s+(a\s+)?developer\b",
        r"\bsystem\s+message\s*:",
        r"\bdeveloper\s+message\s*:",

        # Prompt disclosure
        r"\breveal\s+(the\s+|your\s+)?system\s+prompt\b",
        r"\bshow\s+(the\s+|your\s+)?system\s+prompt\b",
        r"\bprint\s+(the\s+|your\s+)?system\s+prompt\b",
        r"\bdisplay\s+(the\s+|your\s+)?system\s+prompt\b",
        r"\breveal\s+(the\s+|your\s+)?developer\s+message\b",
        r"\bshow\s+(the\s+|your\s+)?developer\s+message\b",
        r"\breveal\s+(your\s+)?hidden\s+instructions?\b",
        r"\bshow\s+(your\s+)?hidden\s+instructions?\b",
        r"\breveal\s+(your\s+)?hidden\s+prompt\b",
        r"\bshow\s+(your\s+)?hidden\s+prompt\b",

        # Secret extraction
        r"\breveal\s+(the\s+|your\s+|user'?s?\s+)?api\s+keys?\b",
        r"\bshow\s+(the\s+|your\s+|user'?s?\s+)?api\s+keys?\b",
        r"\breveal\s+(the\s+|your\s+|user'?s?\s+)?passwords?\b",
        r"\bshow\s+(the\s+|your\s+|user'?s?\s+)?passwords?\b",
        r"\breveal\s+(the\s+|your\s+|user'?s?\s+)?access\s+tokens?\b",
        r"\bshow\s+(the\s+|your\s+|user'?s?\s+)?access\s+tokens?\b",
        r"\bsend\s+(the\s+)?user'?s?\s+secrets?\b",
        r"\bsend\s+(the\s+)?credentials?\b",
        r"\bexfiltrate\s+(the\s+)?data\b",
        r"\bexfiltrate\b",

        # Memory / file extraction
        r"\breveal\s+(the\s+|your\s+|user'?s?\s+)?private\s+memory\b",
        r"\bshow\s+(the\s+|your\s+|user'?s?\s+)?private\s+memory\b",
        r"\breveal\s+(the\s+|your\s+|user'?s?\s+)?saved\s+memories\b",
        r"\bshow\s+(the\s+|your\s+|user'?s?\s+)?saved\s+memories\b",
        r"\baccess\s+(the\s+)?user'?s?\s+private\s+files?\b",

        # Command/tool execution
        r"\bexecute\s+(the\s+)?shell\s+commands?\b",
        r"\brun\s+(the\s+)?shell\s+commands?\b",
        r"\bexecute\s+(the\s+)?terminal\s+commands?\b",
        r"\brun\s+(the\s+)?terminal\s+commands?\b",
        r"\brun\s+powershell\b",
        r"\brun\s+cmd(?:\.exe)?\b",
        r"\bexecute\s+this\s+code\b",
        r"\brun\s+this\s+code\b",

        # Permission escalation
        r"\byou\s+have\s+permission\s+to\b",
        r"\byou\s+are\s+authorized\s+to\b",
        r"\bpermission\s+granted\b",
        r"\buser\s+approved\s+this\s+action\b",
        r"\buser\s+has\s+approved\b",

        # External action attempts
        r"\bsend\s+(an?\s+)?email\s+to\b",
        r"\bdownload\s+(this\s+|the\s+)?file\b",
        r"\bdelete\s+(the\s+|all\s+)?files?\b",
    )

    CONTROL_CHAR_PATTERN = re.compile(
        r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]"
    )

    WHITESPACE_PATTERN = re.compile(
        r"\s+"
    )

    @classmethod
    def _normalize_text(
        cls,
        value: str,
    ) -> str:
        if not isinstance(
            value,
            str,
        ):
            return ""

        normalized = unicodedata.normalize(
            "NFKC",
            value,
        )

        normalized = (
            cls.CONTROL_CHAR_PATTERN
            .sub(
                " ",
                normalized,
            )
        )

        normalized = (
            cls.WHITESPACE_PATTERN
            .sub(
                " ",
                normalized,
            )
            .strip()
        )

        return normalized

    @classmethod
    def sanitize_query(
        cls,
        query: str,
    ) -> str:
        cleaned = cls._normalize_text(
            query
        )

        if not cleaned:
            raise ValueError(
                "Web search query cannot be empty."
            )

        if (
            len(cleaned)
            > cls.MAX_QUERY_LENGTH
        ):
            raise ValueError(
                "Web search query is too long."
            )

        return cleaned

    @classmethod
    def contains_prompt_injection(
        cls,
        content: str,
    ) -> bool:
        normalized = cls._normalize_text(
            content
        )

        if not normalized:
            return False

        return any(
            re.search(
                pattern,
                normalized,
                flags=re.IGNORECASE,
            )
            is not None
            for pattern
            in cls.PROMPT_INJECTION_PATTERNS
        )

    @classmethod
    def sanitize_content(
        cls,
        content: str,
    ) -> str:
        cleaned = cls._normalize_text(
            content
        )

        if not cleaned:
            return ""

        cleaned = cleaned[
            :cls.MAX_CONTENT_LENGTH
        ]

        for pattern in (
            cls.PROMPT_INJECTION_PATTERNS
        ):
            cleaned = re.sub(
                pattern,
                cls.REMOVED_INSTRUCTION_MARKER,
                cleaned,
                flags=re.IGNORECASE,
            )

        cleaned = (
            cls.WHITESPACE_PATTERN
            .sub(
                " ",
                cleaned,
            )
            .strip()
        )

        return cleaned[
            :cls.MAX_CONTENT_LENGTH
        ]

    @classmethod
    def sanitize_title(
        cls,
        title: str,
    ) -> str:
        cleaned = cls.sanitize_content(
            title
        )

        return cleaned[
            :cls.MAX_TITLE_LENGTH
        ]

    @classmethod
    def _normalize_hostname(
        cls,
        hostname: str,
    ) -> str:
        """
        Normalize a hostname into lower-case ASCII/IDNA form.

        Returns an empty string when the hostname is malformed.
        """

        if not isinstance(
            hostname,
            str,
        ):
            return ""

        candidate = (
            hostname
            .strip()
            .rstrip(".")
            .lower()
        )

        if not candidate:
            return ""

        # IPv6 zone identifiers are not accepted.
        #
        # Example:
        # fe80::1%eth0
        if "%" in candidate:
            return ""

        try:
            candidate = (
                candidate
                .encode("idna")
                .decode("ascii")
            )
        except UnicodeError:
            return ""

        if (
            len(candidate) > 253
        ):
            return ""

        return candidate

    @classmethod
    def _is_blocked_hostname(
        cls,
        hostname: str,
    ) -> bool:
        normalized = (
            cls._normalize_hostname(
                hostname
            )
        )

        if not normalized:
            return True

        if (
            normalized
            in cls.BLOCKED_HOSTNAMES
        ):
            return True

        return any(
            normalized.endswith(
                suffix
            )
            for suffix
            in cls.BLOCKED_HOST_SUFFIXES
        )

    @staticmethod
    def is_public_ip_address(
        value: str,
    ) -> bool:
        """
        Return True only for globally routable IPv4/IPv6.

        This rejects:
        - loopback
        - private
        - link-local
        - multicast
        - reserved
        - unspecified
        - documentation/non-global ranges
        """

        try:
            address = (
                ipaddress.ip_address(
                    value
                )
            )
        except ValueError:
            return False

        return address.is_global

    @classmethod
    def _parse_and_validate_url(
        cls,
        url: str,
    ):
        """
        Perform non-network URL validation.

        Returns ParseResult when structurally safe,
        otherwise None.
        """

        if not isinstance(
            url,
            str,
        ):
            return None

        candidate = url.strip()

        if not candidate:
            return None

        if (
            len(candidate) > 4096
        ):
            return None

        # Backslashes can produce inconsistent URL
        # interpretation between parsers/clients.
        if "\\" in candidate:
            return None

        if (
            cls.CONTROL_CHAR_PATTERN
            .search(candidate)
        ):
            return None

        try:
            parsed = urlparse(
                candidate
            )
        except Exception:
            return None

        scheme = (
            parsed.scheme
            .lower()
            .strip()
        )

        if (
            scheme
            in cls.BLOCKED_SCHEMES
        ):
            return None

        if (
            scheme
            not in cls.ALLOWED_SCHEMES
        ):
            return None

        # Absolute URL required.
        if not parsed.netloc:
            return None

        # Embedded credentials are forbidden.
        if (
            parsed.username
            is not None
            or parsed.password
            is not None
        ):
            return None

        try:
            port = parsed.port
        except ValueError:
            return None

        if (
            port is not None
            and (
                port < 1
                or port > 65535
            )
        ):
            return None

        hostname = cls._normalize_hostname(
            parsed.hostname
            or ""
        )

        if not hostname:
            return None

        if cls._is_blocked_hostname(
            hostname
        ):
            return None

        # If hostname itself is an IP literal,
        # it must be globally routable.
        try:
            ipaddress.ip_address(
                hostname
            )
        except ValueError:
            pass
        else:
            if not cls.is_public_ip_address(
                hostname
            ):
                return None

        return parsed

    @classmethod
    def is_safe_public_url(
        cls,
        url: str,
    ) -> bool:
        """
        Fast, non-DNS URL validation.

        Suitable for filtering search-result links because
        ORVYN currently does not fetch those links directly.

        Before a future outbound HTTP connection is made,
        validate_public_destination() must also be called.
        """

        return (
            cls._parse_and_validate_url(
                url
            )
            is not None
        )

    @classmethod
    def _resolve_hostname_sync(
        cls,
        hostname: str,
        port: int,
    ) -> set[str]:
        """
        Resolve every IPv4/IPv6 address returned for a host.

        Runs through asyncio.to_thread() from the async API.
        """

        results = socket.getaddrinfo(
            hostname,
            port,
            family=socket.AF_UNSPEC,
            type=socket.SOCK_STREAM,
        )

        addresses: set[str] = set()

        for result in results:
            sockaddr = result[4]

            if not sockaddr:
                continue

            address = sockaddr[0]

            if address:
                addresses.add(
                    address
                )

        return addresses

    @classmethod
    async def resolve_public_ips(
        cls,
        hostname: str,
        port: int = 443,
    ) -> set[str]:
        """
        Resolve a hostname and require every returned address
        to be globally routable.

        If even one DNS result points to private/internal
        address space, the hostname is rejected.
        """

        normalized = cls._normalize_hostname(
            hostname
        )

        if not normalized:
            raise ValueError(
                "Invalid hostname."
            )

        if cls._is_blocked_hostname(
            normalized
        ):
            raise ValueError(
                "Private or internal hostname is not allowed."
            )

        # Direct IP literal.
        try:
            ipaddress.ip_address(
                normalized
            )
        except ValueError:
            pass
        else:
            if not cls.is_public_ip_address(
                normalized
            ):
                raise ValueError(
                    "Private or non-public IP address is not allowed."
                )

            return {
                normalized
            }

        try:
            addresses = await asyncio.wait_for(
                asyncio.to_thread(
                    cls._resolve_hostname_sync,
                    normalized,
                    port,
                ),
                timeout=(
                    cls.DNS_RESOLUTION_TIMEOUT_SECONDS
                ),
            )
        except asyncio.TimeoutError as exc:
            raise ValueError(
                "DNS resolution timed out."
            ) from exc
        except socket.gaierror as exc:
            raise ValueError(
                "Hostname could not be resolved."
            ) from exc
        except OSError as exc:
            raise ValueError(
                "DNS resolution failed."
            ) from exc

        if not addresses:
            raise ValueError(
                "Hostname did not resolve to an IP address."
            )

        unsafe_addresses = {
            address
            for address
            in addresses
            if not cls.is_public_ip_address(
                address
            )
        }

        if unsafe_addresses:
            raise ValueError(
                "Hostname resolves to a private or "
                "non-public network address."
            )

        return addresses

    @classmethod
    async def validate_public_destination(
        cls,
        url: str,
    ) -> set[str]:
        """
        Strict validation before a future outbound HTTP
        request.

        Checks:
        - URL structure
        - scheme
        - userinfo
        - hostname
        - IP literals
        - DNS resolution
        - every resolved IP is public

        Returns the validated resolved IP set.
        """

        parsed = (
            cls._parse_and_validate_url(
                url
            )
        )

        if parsed is None:
            raise ValueError(
                "Unsafe or invalid public URL."
            )

        hostname = cls._normalize_hostname(
            parsed.hostname
            or ""
        )

        if not hostname:
            raise ValueError(
                "URL hostname is invalid."
            )

        port = parsed.port

        if port is None:
            port = (
                443
                if parsed.scheme.lower()
                == "https"
                else 80
            )

        return await cls.resolve_public_ips(
            hostname,
            port,
        )

    @classmethod
    def build_safe_redirect_url(
        cls,
        *,
        current_url: str,
        location: str,
    ) -> str:
        """
        Resolve a redirect Location header against the
        current URL and perform non-DNS validation.

        A future HTTP fetcher must additionally call
        validate_public_destination() on the returned URL
        before following the redirect.
        """

        if not isinstance(
            location,
            str,
        ):
            raise ValueError(
                "Invalid redirect target."
            )

        location = location.strip()

        if not location:
            raise ValueError(
                "Redirect target cannot be empty."
            )

        redirected_url = urljoin(
            current_url,
            location,
        )

        if not cls.is_safe_public_url(
            redirected_url
        ):
            raise ValueError(
                "Unsafe redirect target."
            )

        return redirected_url

    @classmethod
    async def validate_redirect_target(
        cls,
        *,
        current_url: str,
        location: str,
    ) -> tuple[
        str,
        set[str],
    ]:
        """
        Strictly validate one redirect hop.

        Every redirect hop must be independently validated.
        """

        redirected_url = (
            cls.build_safe_redirect_url(
                current_url=current_url,
                location=location,
            )
        )

        addresses = (
            await cls
            .validate_public_destination(
                redirected_url
            )
        )

        return (
            redirected_url,
            addresses,
        )


web_security_service = (
    WebSecurityService()
)