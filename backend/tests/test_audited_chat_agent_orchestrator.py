
"""ORVYN Phase 10J-E3C: Audited orchestrator reliability tests."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from uuid import uuid4

import pytest

import app.services.audited_chat_agent_orchestrator as audit_module
from app.services.audited_chat_agent_orchestrator import (
    AuditedChatAgentOrchestrator,
)
from app.tools.multi_step_engine import (
    ArithmeticPlan,
    PlanResult,
    Step,
    StepRecord,
)


class FakeSession:
    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False


class FakeQuota:
    def __init__(self):
        self.acquired = 0
        self.released = 0

    def acquire(self, user_id):
        self.acquired += 1
        return SimpleNamespace(allowed=True, reason=None)

    def release(self, user_id):
        self.released += 1


class FakeAuditService:
    def __init__(
        self,
        session,
        *,
        start_error=None,
        finish_error=None,
    ):
        self.start_error = start_error
        self.finish_error = finish_error
        self.started = []
        self.finished = []

    async def start(self, *, user_id, step_count):
        if self.start_error is not None:
            raise self.start_error

        audit = SimpleNamespace(id=str(uuid4()))
        self.started.append((user_id, step_count, audit.id))
        return audit

    async def finish(
        self,
        *,
        audit_id,
        user_id,
        status,
        completed_steps,
        duration_ms,
        failure_category=None,
    ):
        if self.finish_error is not None:
            raise self.finish_error

        self.finished.append(
            {
                "audit_id": audit_id,
                "user_id": user_id,
                "status": status,
                "completed_steps": completed_steps,
                "duration_ms": duration_ms,
                "failure_category": failure_category,
            }
        )
        return SimpleNamespace(status=status)


class FakeEngine:
    def __init__(self, result=None, error=None):
        self.result = result
        self.error = error
        self.calls = 0

    async def execute(self, **kwargs):
        self.calls += 1

        if self.error is not None:
            raise self.error

        return self.result


class BlockingEngine:
    def __init__(self):
        self.started = asyncio.Event()

    async def execute(self, **kwargs):
        self.started.set()
        await asyncio.Event().wait()


def make_plan():
    return ArithmeticPlan(
        steps=[
            Step(id="base", expression="2500 * 18"),
            Step(
                id="percentage",
                expression="$base * 12 / 100",
            ),
        ]
    )


def make_success_result():
    return PlanResult(
        status="succeeded",
        records=(
            StepRecord(
                step_id="base",
                expression="2500 * 18",
                result="45000",
                execution_id=str(uuid4()),
            ),
            StepRecord(
                step_id="percentage",
                expression="(45000) * 12 / 100",
                result="5400",
                execution_id=str(uuid4()),
            ),
        ),
        final_result="5400",
        message="All steps completed.",
    )


def make_timeout_result():
    return PlanResult(
        status="failed",
        records=(),
        final_result=None,
        message=(
            "The calculation exceeded its execution time limit."
        ),
    )


@pytest.fixture
def setup_audited_orchestrator(monkeypatch):
    def factory(
        *,
        result=None,
        engine_error=None,
        start_error=None,
        finish_error=None,
        engine=None,
    ):
        quota = FakeQuota()
        audit_service = FakeAuditService(
            None,
            start_error=start_error,
            finish_error=finish_error,
        )

        monkeypatch.setattr(
            audit_module,
            "AsyncSessionLocal",
            lambda: FakeSession(),
        )

        monkeypatch.setattr(
            audit_module,
            "AgentExecutionAuditService",
            lambda session: audit_service,
        )

        orchestrator = AuditedChatAgentOrchestrator(
            runner=SimpleNamespace(),
            quota=quota,
        )

        execution_engine = engine or FakeEngine(
            result=result,
            error=engine_error,
        )

        orchestrator._multi_step_engine = execution_engine

        return (
            orchestrator,
            execution_engine,
            audit_service,
            quota,
        )

    return factory


async def execute_plan(orchestrator, user_id):
    return await orchestrator._execute_multi_step(
        plan=make_plan(),
        user_id=user_id,
        conversation_id=None,
        message_id=None,
    )


@pytest.mark.asyncio
async def test_success_creates_and_finishes_audit(
    setup_audited_orchestrator,
):
    orchestrator, engine, audit, quota = (
        setup_audited_orchestrator(
            result=make_success_result(),
        )
    )

    decision = await execute_plan(
        orchestrator,
        uuid4(),
    )

    assert decision.status == "succeeded"
    assert decision.tool_name == "multi_step_calculator"
    assert engine.calls == 1

    assert len(audit.started) == 1
    assert len(audit.finished) == 1

    record = audit.finished[0]
    assert record["status"] == "succeeded"
    assert record["completed_steps"] == 2
    assert record["failure_category"] is None
    assert record["duration_ms"] >= 0

    assert quota.acquired == 1
    assert quota.released == 1


@pytest.mark.asyncio
async def test_audit_start_failure_blocks_execution(
    setup_audited_orchestrator,
):
    orchestrator, engine, audit, quota = (
        setup_audited_orchestrator(
            result=make_success_result(),
            start_error=RuntimeError(
                "Simulated database failure"
            ),
        )
    )

    decision = await execute_plan(
        orchestrator,
        uuid4(),
    )

    assert decision.status == "failed"
    assert "Simulated database failure" not in decision.response

    assert engine.calls == 0
    assert audit.finished == []
    assert quota.released == 1


@pytest.mark.asyncio
async def test_audit_finalization_failure_prevents_success(
    setup_audited_orchestrator,
):
    orchestrator, engine, audit, quota = (
        setup_audited_orchestrator(
            result=make_success_result(),
            finish_error=RuntimeError(
                "Simulated audit finalization failure"
            ),
        )
    )

    decision = await execute_plan(
        orchestrator,
        uuid4(),
    )

    assert engine.calls == 1
    assert decision.status == "failed"
    assert "Simulated audit finalization failure" not in (
        decision.response
    )
    assert quota.released == 1


@pytest.mark.asyncio
async def test_timeout_is_recorded_as_failed(
    setup_audited_orchestrator,
):
    orchestrator, engine, audit, quota = (
        setup_audited_orchestrator(
            result=make_timeout_result(),
        )
    )

    decision = await execute_plan(
        orchestrator,
        uuid4(),
    )

    assert decision.status == "failed"
    assert engine.calls == 1

    assert len(audit.finished) == 1
    record = audit.finished[0]

    assert record["status"] == "failed"
    assert record["failure_category"] == "timeout"
    assert record["completed_steps"] == 0
    assert quota.released == 1


@pytest.mark.asyncio
async def test_unexpected_engine_failure_is_audited(
    setup_audited_orchestrator,
):
    orchestrator, engine, audit, quota = (
        setup_audited_orchestrator(
            engine_error=RuntimeError(
                "Internal engine failure"
            ),
        )
    )

    decision = await execute_plan(
        orchestrator,
        uuid4(),
    )

    assert decision.status == "failed"
    assert engine.calls == 1

    assert len(audit.finished) == 1
    assert audit.finished[0]["status"] == "failed"
    assert (
        audit.finished[0]["failure_category"]
        == "unexpected_error"
    )
    assert quota.released == 1


@pytest.mark.asyncio
async def test_cancellation_is_propagated_and_audited(
    setup_audited_orchestrator,
):
    blocking_engine = BlockingEngine()

    orchestrator, engine, audit, quota = (
        setup_audited_orchestrator(
            engine=blocking_engine,
        )
    )

    task = asyncio.create_task(
        execute_plan(orchestrator, uuid4())
    )

    await asyncio.wait_for(
        blocking_engine.started.wait(),
        timeout=2,
    )

    task.cancel()

    with pytest.raises(asyncio.CancelledError):
        await asyncio.wait_for(task, timeout=2)

    assert len(audit.finished) == 1
    assert audit.finished[0]["status"] == "cancelled"
    assert audit.finished[0]["failure_category"] == "cancelled"
    assert quota.released == 1


@pytest.mark.asyncio
async def test_failed_verification_never_returns_success(
    setup_audited_orchestrator,
):
    invalid_result = PlanResult(
        status="succeeded",
        records=(
            StepRecord(
                step_id="base",
                expression="2500 * 18",
                result="45000",
                execution_id=str(uuid4()),
            ),
        ),
        final_result="45000",
        message="Incomplete result.",
    )

    orchestrator, engine, audit, quota = (
        setup_audited_orchestrator(
            result=invalid_result,
        )
    )

    decision = await execute_plan(
        orchestrator,
        uuid4(),
    )

    assert decision.status == "failed"
    assert engine.calls == 1

    assert audit.finished[0]["status"] == "failed"
    assert (
        audit.finished[0]["failure_category"]
        == "verification_failed"
    )
    assert quota.released == 1
