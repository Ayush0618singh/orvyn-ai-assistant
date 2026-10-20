
"""ORVYN Phase 10J-E7F.

Regression tests for audited agent heartbeat supervision.

Coverage:
- Execution and heartbeat finishing together
- Heartbeat failure after successful tool execution
- Cancellation during heartbeat activity
- Quota cleanup after failures
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from uuid import uuid4

import pytest

import app.services.audited_chat_agent_orchestrator as module
from app.services.audited_chat_agent_orchestrator import (
    AuditedChatAgentOrchestrator,
)


class FakeSession:
    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False


class RecordingQuota:
    def __init__(self):
        self.acquired = 0
        self.released = 0

    def acquire(self, user_id):
        self.acquired += 1
        return SimpleNamespace(
            allowed=True,
            reason=None,
        )

    def release(self, user_id):
        self.released += 1


class RecordingAudit:
    started = []
    finished = []

    def __init__(self, session):
        self.session = session

    async def start(self, *, user_id, step_count):
        audit_id = str(uuid4())

        self.started.append(audit_id)

        return SimpleNamespace(id=audit_id)

    async def finish(self, **kwargs):
        self.finished.append(kwargs)

        return SimpleNamespace(
            status=kwargs["status"],
        )


class ControlledEngine:
    def __init__(self):
        self.started = asyncio.Event()
        self.release = asyncio.Event()
        self.cancelled = False

    async def execute(self, **kwargs):
        self.started.set()

        try:
            await self.release.wait()

            return SimpleNamespace(
                status="succeeded",
                final_result=50,
                message="Completed",
                records=[
                    SimpleNamespace(
                        step_id="first",
                        expression="10 * 5",
                        result=50,
                        execution_id=str(uuid4()),
                    )
                ],
            )

        except asyncio.CancelledError:
            self.cancelled = True
            raise


class ControlledHeartbeat:
    def __init__(self):
        self.started = asyncio.Event()
        self.release = asyncio.Event()
        self.fail = False

    async def run(
        self,
        *,
        audit_id,
        user_id,
        stop_event,
    ):
        self.started.set()

        await self.release.wait()

        if self.fail:
            raise RuntimeError(
                "Controlled heartbeat failure"
            )

        await stop_event.wait()


def make_orchestrator(
    monkeypatch,
    heartbeat,
):
    RecordingAudit.started = []
    RecordingAudit.finished = []

    monkeypatch.setattr(
        module,
        "AsyncSessionLocal",
        lambda: FakeSession(),
    )

    monkeypatch.setattr(
        module,
        "AgentExecutionAuditService",
        RecordingAudit,
    )

    quota = RecordingQuota()
    engine = ControlledEngine()

    orchestrator = AuditedChatAgentOrchestrator(
        runner=SimpleNamespace(),
        quota=quota,
    )

    orchestrator._multi_step_engine = engine

    monkeypatch.setattr(
        orchestrator,
        "_heartbeat_loop",
        heartbeat.run,
    )

    return orchestrator, engine, quota


def make_plan():
    from app.tools.multi_step_engine import (
        ArithmeticPlan,
        Step,
    )

    return ArithmeticPlan(
        steps=[
            Step(
                id="first",
                expression="10 * 5",
            )
        ]
    )


async def execute(orchestrator):
    return await orchestrator._execute_multi_step(
        plan=make_plan(),
        user_id=uuid4(),
        conversation_id=None,
        message_id=None,
    )


@pytest.mark.asyncio
async def test_heartbeat_failure_cancels_active_execution(
    monkeypatch,
):
    heartbeat = ControlledHeartbeat()

    orchestrator, engine, quota = make_orchestrator(
        monkeypatch,
        heartbeat,
    )

    task = asyncio.create_task(
        execute(orchestrator)
    )

    await asyncio.wait_for(
        engine.started.wait(),
        timeout=2,
    )

    await asyncio.wait_for(
        heartbeat.started.wait(),
        timeout=2,
    )

    heartbeat.fail = True
    heartbeat.release.set()

    decision = await asyncio.wait_for(
        task,
        timeout=2,
    )

    assert decision.status == "failed"
    assert engine.cancelled is True

    assert quota.acquired == 1
    assert quota.released == 1

    assert len(RecordingAudit.finished) == 1
    assert RecordingAudit.finished[0]["status"] == "failed"


@pytest.mark.asyncio
async def test_simultaneous_success_and_heartbeat_failure(
    monkeypatch,
):
    heartbeat = ControlledHeartbeat()

    orchestrator, engine, quota = make_orchestrator(
        monkeypatch,
        heartbeat,
    )

    task = asyncio.create_task(
        execute(orchestrator)
    )

    await asyncio.wait_for(
        engine.started.wait(),
        timeout=2,
    )

    await asyncio.wait_for(
        heartbeat.started.wait(),
        timeout=2,
    )

    heartbeat.fail = True

    engine.release.set()
    heartbeat.release.set()

    decision = await asyncio.wait_for(
        task,
        timeout=2,
    )

    # An invalid heartbeat must never produce audited success.
    assert decision.status == "failed"

    assert quota.released == 1
    assert len(RecordingAudit.finished) == 1
    assert RecordingAudit.finished[0]["status"] == "failed"


@pytest.mark.asyncio
async def test_external_cancellation_releases_quota(
    monkeypatch,
):
    heartbeat = ControlledHeartbeat()

    orchestrator, engine, quota = make_orchestrator(
        monkeypatch,
        heartbeat,
    )

    task = asyncio.create_task(
        execute(orchestrator)
    )

    await asyncio.wait_for(
        engine.started.wait(),
        timeout=2,
    )

    await asyncio.wait_for(
        heartbeat.started.wait(),
        timeout=2,
    )

    # Release heartbeat so cleanup can finish.
    heartbeat.release.set()

    task.cancel()

    with pytest.raises(asyncio.CancelledError):
        await asyncio.wait_for(
            task,
            timeout=2,
        )

    assert engine.cancelled is True
    assert quota.acquired == 1
    assert quota.released == 1

    assert len(RecordingAudit.finished) == 1
    assert RecordingAudit.finished[0]["status"] == "cancelled"
