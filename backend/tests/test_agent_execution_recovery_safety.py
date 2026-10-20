
"""Tests for process-local execution tracking."""

from uuid import uuid4

import pytest

from app.services.agent_execution_recovery_safety import (
    ActiveExecutionRegistry,
)


def test_execution_tracking_lifecycle():
    registry = ActiveExecutionRegistry()
    execution_id = uuid4()

    assert not registry.is_active(execution_id)

    with registry.track(execution_id):
        assert registry.is_active(execution_id)
        assert execution_id in registry.snapshot()

    assert not registry.is_active(execution_id)


def test_tracking_cleans_up_after_failure():
    registry = ActiveExecutionRegistry()
    execution_id = uuid4()

    with pytest.raises(RuntimeError):
        with registry.track(execution_id):
            raise RuntimeError("Simulated failure")

    assert not registry.is_active(execution_id)


def test_duplicate_registration_rejected():
    registry = ActiveExecutionRegistry()
    execution_id = uuid4()

    registry.register(execution_id)

    with pytest.raises(ValueError):
        registry.register(execution_id)

    registry.unregister(execution_id)

    assert registry.snapshot() == frozenset()


def test_multiple_executions_tracked_independently():
    registry = ActiveExecutionRegistry()

    first = uuid4()
    second = uuid4()

    registry.register(first)
    registry.register(second)

    registry.unregister(first)

    assert not registry.is_active(first)
    assert registry.is_active(second)

    registry.unregister(second)

    assert registry.snapshot() == frozenset()


@pytest.mark.parametrize(
    "invalid_id",
    [None, "invalid", 123, True],
)
def test_invalid_execution_identity_rejected(invalid_id):
    registry = ActiveExecutionRegistry()

    with pytest.raises(TypeError):
        registry.register(invalid_id)

    with pytest.raises(TypeError):
        registry.unregister(invalid_id)

    with pytest.raises(TypeError):
        registry.is_active(invalid_id)
