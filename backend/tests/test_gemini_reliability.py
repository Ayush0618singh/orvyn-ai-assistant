
from __future__ import annotations

import asyncio

import pytest

from app.ai.providers import reliable_gemini
from app.ai.providers.reliable_gemini import (
    GeminiReliabilityError,
    ReliableGeminiProvider,
)


def make_provider():
    # Avoid real API client initialization.
    return ReliableGeminiProvider.__new__(
        ReliableGeminiProvider
    )


@pytest.fixture
def models(monkeypatch):
    monkeypatch.setattr(
        reliable_gemini.settings,
        "llm_model",
        "test-primary",
    )
    monkeypatch.setattr(
        reliable_gemini.settings,
        "gemini_fallback_model",
        "test-fallback",
    )
    monkeypatch.setattr(
        reliable_gemini,
        "RETRY_DELAY_SECONDS",
        0.0,
    )


@pytest.mark.asyncio
async def test_primary_success(models):
    provider = make_provider()
    calls = []

    async def operation(model):
        calls.append(model)
        return "success"

    result = await provider._with_reliability(
        operation=operation,
        operation_name="test",
    )

    assert result == "success"
    assert calls == ["test-primary"]


@pytest.mark.asyncio
async def test_primary_timeout_then_success(models):
    provider = make_provider()
    calls = []

    async def operation(model):
        calls.append(model)

        if len(calls) == 1:
            raise TimeoutError()

        return "recovered"

    result = await provider._with_reliability(
        operation=operation,
        operation_name="test",
    )

    assert result == "recovered"
    assert calls == [
        "test-primary",
        "test-primary",
    ]


@pytest.mark.asyncio
async def test_fallback_after_primary_timeouts(models):
    provider = make_provider()
    calls = []

    async def operation(model):
        calls.append(model)

        if model == "test-primary":
            raise TimeoutError()

        return "fallback-success"

    result = await provider._with_reliability(
        operation=operation,
        operation_name="test",
    )

    assert result == "fallback-success"
    assert calls == [
        "test-primary",
        "test-primary",
        "test-fallback",
    ]


@pytest.mark.asyncio
async def test_all_models_unavailable(models):
    provider = make_provider()
    calls = []

    async def operation(model):
        calls.append(model)
        raise TimeoutError()

    with pytest.raises(GeminiReliabilityError):
        await provider._with_reliability(
            operation=operation,
            operation_name="test",
        )

    assert len(calls) == 3


@pytest.mark.asyncio
async def test_non_retryable_error_fails_immediately(models):
    provider = make_provider()
    calls = []

    async def operation(model):
        calls.append(model)
        raise ValueError("invalid schema")

    with pytest.raises(GeminiReliabilityError):
        await provider._with_reliability(
            operation=operation,
            operation_name="test",
        )

    assert calls == ["test-primary"]


@pytest.mark.asyncio
async def test_cancelled_task_is_not_swallowed(models):
    provider = make_provider()

    async def operation(model):
        raise asyncio.CancelledError()

    with pytest.raises(asyncio.CancelledError):
        await provider._with_reliability(
            operation=operation,
            operation_name="test",
        )


@pytest.mark.asyncio
async def test_same_primary_and_fallback_not_duplicated(
    models,
    monkeypatch,
):
    monkeypatch.setattr(
        reliable_gemini.settings,
        "gemini_fallback_model",
        "test-primary",
    )

    provider = make_provider()
    calls = []

    async def operation(model):
        calls.append(model)
        raise TimeoutError()

    with pytest.raises(GeminiReliabilityError):
        await provider._with_reliability(
            operation=operation,
            operation_name="test",
        )

    assert calls == [
        "test-primary",
        "test-primary",
    ]


@pytest.mark.asyncio
async def test_real_async_timeout_is_enforced(
    models,
    monkeypatch,
):
    monkeypatch.setattr(
        reliable_gemini,
        "REQUEST_TIMEOUT_SECONDS",
        0.01,
    )

    provider = make_provider()
    calls = []

    async def operation(model):
        calls.append(model)
        await asyncio.sleep(0.2)
        return "too-late"

    with pytest.raises(GeminiReliabilityError):
        await provider._with_reliability(
            operation=operation,
            operation_name="test",
        )

    assert len(calls) == 3
