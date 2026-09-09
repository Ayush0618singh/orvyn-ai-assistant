from datetime import (
    datetime,
    timezone,
)

import pytest

from app.services.web_freshness_service import (
    WebFreshnessService,
    web_freshness_service,
)


@pytest.mark.parametrize(
    "message",
    [
        "Latest Python release kya hai?",
        "AI news today",
        "Current Bitcoin price kya hai?",
        "Search the web for FastAPI updates",
        "Aaj ka weather kya hai?",
        "Latest election results",
        "What is the exchange rate today?",
        "Check the web for this information",
        "Flight status kya hai?",
    ],
)
def test_live_queries_require_verification(
    message: str,
):
    assert (
        web_freshness_service
        .requires_live_verification(
            message
        )
        is True
    )


@pytest.mark.parametrize(
    "message",
    [
        "What is binary search?",
        "Explain OOP",
        "What is normalization in DBMS?",
        "Explain linked list",
        "What is REST API?",
        "How does merge sort work?",
        "Explain inheritance in Java",
    ],
)
def test_stable_queries_do_not_require_live_verification(
    message: str,
):
    assert (
        web_freshness_service
        .requires_live_verification(
            message
        )
        is False
    )


def test_empty_message_does_not_require_live_verification():
    assert (
        web_freshness_service
        .requires_live_verification("")
        is False
    )


def test_whitespace_message_does_not_require_live_verification():
    assert (
        web_freshness_service
        .requires_live_verification(
            "       "
        )
        is False
    )


def test_recent_year_release_requires_verification():
    current_year = (
        datetime.now(
            timezone.utc
        ).year
    )

    message = (
        f"Python {current_year} release details"
    )

    assert (
        web_freshness_service
        .requires_live_verification(
            message
        )
        is True
    )


def test_recent_year_model_requires_verification():
    current_year = (
        datetime.now(
            timezone.utc
        ).year
    )

    message = (
        f"Gemini {current_year} model"
    )

    assert (
        web_freshness_service
        .requires_live_verification(
            message
        )
        is True
    )


def test_old_year_stable_question_does_not_trigger_year_guard():
    current_year = (
        datetime.now(
            timezone.utc
        ).year
    )

    old_year = (
        current_year - 10
    )

    message = (
        f"Explain the Python {old_year} release"
    )

    assert (
        web_freshness_service
        .requires_live_verification(
            message
        )
        is False
    )


def test_english_style_detection():
    assert (
        WebFreshnessService
        ._response_style(
            "What is the latest Python release?"
        )
        == "english"
    )


def test_hinglish_style_detection():
    assert (
        WebFreshnessService
        ._response_style(
            "Latest Python release kya hai?"
        )
        == "hinglish"
    )


def test_hindi_style_detection():
    assert (
        WebFreshnessService
        ._response_style(
            "आज का मौसम क्या है?"
        )
        == "hindi"
    )


def test_web_disabled_english_response_is_honest():
    response = (
        web_freshness_service
        .build_unavailable_response(
            message=(
                "What is the latest Python release?"
            ),
            reason="web_disabled",
        )
    )

    lowered = response.lower()

    assert response.strip()
    assert "web" in lowered
    assert "disabled" in lowered
    assert "guess" in lowered


def test_web_disabled_hinglish_response_is_honest():
    response = (
        web_freshness_service
        .build_unavailable_response(
            message=(
                "Latest Python release kya hai?"
            ),
            reason="web_disabled",
        )
    )

    lowered = response.lower()

    assert response.strip()
    assert "web" in lowered
    assert "off" in lowered
    assert "guess" in lowered


def test_web_disabled_hindi_response_is_honest():
    response = (
        web_freshness_service
        .build_unavailable_response(
            message=(
                "आज का मौसम क्या है?"
            ),
            reason="web_disabled",
        )
    )

    assert response.strip()

    assert (
        "वेब"
        in response
    )


@pytest.mark.parametrize(
    "reason",
    [
        "search_failed",
        "no_results",
        "unusable_results",
    ],
)
def test_all_known_failure_reasons_return_response(
    reason: str,
):
    response = (
        web_freshness_service
        .build_unavailable_response(
            message=(
                "What is the latest Python release?"
            ),
            reason=reason,
        )
    )

    assert isinstance(
        response,
        str,
    )

    assert response.strip()


@pytest.mark.parametrize(
    "reason",
    [
        "search_failed",
        "no_results",
        "unusable_results",
    ],
)
def test_failure_responses_do_not_claim_success(
    reason: str,
):
    response = (
        web_freshness_service
        .build_unavailable_response(
            message=(
                "Latest Python release kya hai?"
            ),
            reason=reason,
        )
    ).lower()

    forbidden_success_claims = (
        "i verified",
        "verified successfully",
        "search successful",
        "confirmed latest",
    )

    for claim in forbidden_success_claims:
        assert (
            claim
            not in response
        )


def test_unknown_failure_reason_falls_back_safely():
    response = (
        web_freshness_service
        .build_unavailable_response(
            message=(
                "Latest Python release kya hai?"
            ),
            reason="unexpected_internal_reason",
        )
    )

    lowered = response.lower()

    assert response.strip()

    assert (
        "search"
        in lowered
        or "web"
        in lowered
    )

    assert (
        "guess"
        in lowered
        or "verification"
        in lowered
    )