
"""Validation tests for recovery and monitoring inputs."""

import pytest

from app.services.agent_execution_recovery_service import (
    AgentExecutionRecoveryService,
)
from app.services.agent_execution_monitoring_service import (
    AgentExecutionMonitoringService,
)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "minutes",
    [-1, 0, 14, 1441, True, "60", None],
)
async def test_recovery_rejects_invalid_stale_minutes(minutes):
    service = AgentExecutionRecoveryService(None)

    with pytest.raises(ValueError):
        await service.recover_stale(
            stale_after_minutes=minutes
        )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "batch_size",
    [0, -1, 101, True, "10", None],
)
async def test_recovery_rejects_invalid_batch_sizes(batch_size):
    service = AgentExecutionRecoveryService(None)

    with pytest.raises(ValueError):
        await service.recover_stale(
            batch_size=batch_size
        )


@pytest.mark.asyncio
async def test_recovery_rejects_invalid_dry_run():
    service = AgentExecutionRecoveryService(None)

    with pytest.raises(TypeError):
        await service.recover_stale(dry_run="false")


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "user_id",
    ["", " ", None, 123],
)
async def test_monitoring_rejects_invalid_user_id(user_id):
    service = AgentExecutionMonitoringService(None)

    with pytest.raises(ValueError):
        await service.get_metrics(user_id=user_id)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "minutes",
    [-1, 0, 14, 1441, True, "60"],
)
async def test_monitoring_rejects_invalid_stale_minutes(minutes):
    service = AgentExecutionMonitoringService(None)

    with pytest.raises(ValueError):
        await service.get_metrics(
            user_id=str(__import__("uuid").uuid4()),
            stale_after_minutes=minutes,
        )
