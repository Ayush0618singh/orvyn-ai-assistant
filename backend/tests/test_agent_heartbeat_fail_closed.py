
"""Fail-closed heartbeat and execution cancellation tests."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from uuid import uuid4

import pytest

import app.services.audited_chat_agent_orchestrator as module
from app.services.audited_chat_agent_orchestrator import (
    AuditedChatAgentOrchestrator,
)
from app.tools.multi_step_engine import ArithmeticPlan, Step


class FakeSession:
    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False


class FakeQuota:
    def __init__(self):
        self.released = 0

    def acquire(self, user_id):
        return SimpleNamespace(
            allowed=True,
            reason=None,
        )

    def release(self, user_id):
        self.released += 1


class FakeAudit:
    def __init__(self, session):
        self.session = session

    async def start(self, *, user_id, step_count):
        return SimpleNamespace(id=str(uuid4()))

    async def finish(self, **kwargs):
        return SimpleNamespace(status=kwargs["status"])


class BlockingEngine:
    def __init__(self):
        self.started = asyncio.Event()
        self.cancelled = False

    async def execute(self, **kwargs):
        self.started.set()

        try:
            await asyncio.Event().wait()

        except asyncio.CancelledError:
            self.cancelled = True
            raise


class ImmediateFailureHeartbeat:
    def __init__(self, session):
        pass

    async def heartbeat(self, **kwargs):
        return False


class ErrorHeartbeat:
    def __init__(self, session):
        pass

    async def heartbeat(self, **kwargs):
        raise RuntimeError("Simulated database error")


def make_plan():
    return ArithmeticPlan(
        steps=[
            Step(
                id="first",
                expression="10 * 5",
            )
        ]
    )


def make_orchestrator(monkeypatch, heartbeat_service):
    monkeypatch.setattr(
        module,
        "AsyncSessionLocal",
        lambda: FakeSession(),
    )

    monkeypatch.setattr(
        module,
        "AgentExecutionAuditService",
        FakeAudit,
    )

    monkeypatch.setattr(
        module,
        "AgentExecutionHeartbeatService",
        heartbeat_service,
    )

    quota = FakeQuota()
    engine = BlockingEngine()

    orchestrator = AuditedChatAgentOrchestrator(
        runner=SimpleNamespace(),
        quota=quota,
    )

    orchestrator._multi_step_engine = engine
    orchestrator.HEARTBEAT_INTERVAL_SECONDS = 0.01

    return orchestrator, engine, quota


async def run_plan(orchestrator):
    return await orchestrator._execute_multi_step(
        plan=make_plan(),
        user_id=uuid4(),
        conversation_id=None,
        message_id=None,
    )


@pytest.mark.asyncio
async def test_rejected_heartbeat_cancels_running_execution(
    monkeypatch,
):
    orchestrator, engine, quota = make_orchestrator(
        monkeypatch,
        ImmediateFailureHeartbeat,
    )

    decision = await asyncio.wait_for(
        run_plan(orchestrator),
        timeout=2,
    )

    assert decision.status == "failed"
    assert engine.cancelled is True
    assert quota.released == 1


@pytest.mark.asyncio
async def test_heartbeat_exception_cancels_running_execution(
    monkeypatch,
):
    orchestrator, engine, quota = make_orchestrator(
        monkeypatch,
        ErrorHeartbeat,
    )

    decision = await asyncio.wait_for(
        run_plan(orchestrator),
        timeout=2,
    )

    assert decision.status == "failed"
    assert engine.cancelled is True
    assert quota.released == 1


@pytest.mark.asyncio
async def test_external_cancellation_stops_execution(
    monkeypatch,
):
    orchestrator, engine, quota = make_orchestrator(
        monkeypatch,
        ImmediateFailureHeartbeat,
    )

    # Prevent heartbeat failure so external cancellation
    # is the only cancellation source.
    orchestrator.HEARTBEAT_INTERVAL_SECONDS = 100

    task = asyncio.create_task(
        run_plan(orchestrator)
    )

    await asyncio.wait_for(
        engine.started.wait(),
        timeout=2,
    )

    task.cancel()

    with pytest.raises(asyncio.CancelledError):
        await asyncio.wait_for(task, timeout=2)

    assert engine.cancelled is True
    assert quota.released == 1
