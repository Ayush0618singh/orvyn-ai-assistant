
"""ORVYN Phase 10J-E2 execution quota tests."""

import asyncio
from uuid import uuid4

import pytest

from app.tools.execution_quota import (
    MultiStepExecutionQuota,
)
from app.services.chat_agent_orchestrator import (
    ChatAgentOrchestrator,
)
from app.tools.multi_step_engine import (
    ArithmeticPlan,
    Step,
)


def make_quota(
    *,
    per_user=2,
    global_limit=3,
    rate=10,
    window=60,
):
    return MultiStepExecutionQuota(
        max_active_per_user=per_user,
        max_active_global=global_limit,
        max_starts_per_window=rate,
        window_seconds=window,
    )


def test_admission_and_release():
    quota = make_quota()
    user = uuid4()

    assert quota.acquire(user).allowed
    assert quota.active_count(user) == 1
    assert quota.active_count() == 1

    quota.release(user)

    assert quota.active_count(user) == 0
    assert quota.active_count() == 0


def test_per_user_concurrency_limit():
    quota = make_quota(per_user=1)
    user = uuid4()

    assert quota.acquire(user).allowed

    rejected = quota.acquire(user)

    assert not rejected.allowed
    assert rejected.reason == "per_user_concurrency_limit"

    quota.release(user)


def test_global_concurrency_limit():
    quota = make_quota(
        per_user=2,
        global_limit=1,
    )

    user_a = uuid4()
    user_b = uuid4()

    assert quota.acquire(user_a).allowed

    rejected = quota.acquire(user_b)

    assert not rejected.allowed
    assert rejected.reason == "global_concurrency_limit"

    quota.release(user_a)


def test_different_users_have_independent_limits():
    quota = make_quota(
        per_user=1,
        global_limit=2,
    )

    user_a = uuid4()
    user_b = uuid4()

    assert quota.acquire(user_a).allowed
    assert quota.acquire(user_b).allowed

    assert quota.active_count(user_a) == 1
    assert quota.active_count(user_b) == 1

    quota.release(user_a)
    quota.release(user_b)


def test_rate_limit_after_completed_requests():
    quota = make_quota(
        per_user=1,
        rate=2,
    )
    user = uuid4()

    for _ in range(2):
        assert quota.acquire(user).allowed
        quota.release(user)

    rejected = quota.acquire(user)

    assert not rejected.allowed
    assert rejected.reason == "per_user_rate_limit"
    assert rejected.retry_after_seconds is not None
    assert rejected.retry_after_seconds > 0
    assert quota.active_count() == 0


def test_rate_limit_is_per_user():
    quota = make_quota(rate=1)

    user_a = uuid4()
    user_b = uuid4()

    assert quota.acquire(user_a).allowed
    quota.release(user_a)

    assert not quota.acquire(user_a).allowed

    assert quota.acquire(user_b).allowed
    quota.release(user_b)


def test_rejected_request_does_not_consume_rate_quota():
    quota = make_quota(
        per_user=1,
        rate=2,
    )
    user = uuid4()

    assert quota.acquire(user).allowed

    # Rejected by concurrency, not charged to rate quota.
    assert not quota.acquire(user).allowed

    quota.release(user)

    # Second successful admission remains available.
    assert quota.acquire(user).allowed
    quota.release(user)

    # Now the rate quota is exhausted.
    assert not quota.acquire(user).allowed


def test_release_without_admission_rejected():
    quota = make_quota()

    with pytest.raises(RuntimeError):
        quota.release(uuid4())


def test_invalid_identity_rejected():
    quota = make_quota()

    with pytest.raises(TypeError):
        quota.acquire("not-a-uuid")

    with pytest.raises(TypeError):
        quota.release("not-a-uuid")


@pytest.mark.parametrize(
    "value",
    [0, -1, True, 10001],
)
def test_invalid_concurrency_configuration(value):
    with pytest.raises(ValueError):
        MultiStepExecutionQuota(
            max_active_per_user=value,
        )


@pytest.mark.parametrize(
    "value",
    [0, -1, True, float("inf"), float("nan")],
)
def test_invalid_window_configuration(value):
    with pytest.raises(ValueError):
        MultiStepExecutionQuota(
            window_seconds=value,
        )


class NeverCalledRunner:
    def __init__(self):
        self.calls = []

    async def run(self, **kwargs):
        self.calls.append(kwargs)
        raise AssertionError(
            "Runner must not execute a denied plan"
        )


class FixedPlanner:
    def plan(self, message):
        return ArithmeticPlan(
            steps=[
                Step(
                    id="first",
                    expression="10 * 5",
                ),
            ]
        )


@pytest.mark.asyncio
async def test_denied_plan_never_calls_runner():
    quota = make_quota(
        per_user=1,
        rate=1,
    )
    user = uuid4()

    assert quota.acquire(user).allowed
    quota.release(user)

    runner = NeverCalledRunner()

    service = ChatAgentOrchestrator(
        runner=runner,
        planner=FixedPlanner(),
        quota=quota,
    )

    decision = await service.process(
        user_message="calculate this",
        user_id=user,
    )

    assert decision.handled is True
    assert decision.status == "denied"
    assert decision.tool_name == "multi_step_calculator"
    assert runner.calls == []


@pytest.mark.asyncio
async def test_failed_plan_releases_slot():
    quota = make_quota(per_user=1)
    user = uuid4()

    runner = NeverCalledRunner()

    service = ChatAgentOrchestrator(
        runner=runner,
        planner=FixedPlanner(),
        quota=quota,
    )

    decision = await service.process(
        user_message="calculate this",
        user_id=user,
    )

    assert decision.status == "failed"
    assert quota.active_count(user) == 0


@pytest.mark.asyncio
async def test_cancelled_plan_releases_slot():
    quota = make_quota(per_user=1)
    user = uuid4()

    started = asyncio.Event()

    class SlowRunner:
        async def run(self, **kwargs):
            started.set()
            await asyncio.sleep(10)

    service = ChatAgentOrchestrator(
        runner=SlowRunner(),
        planner=FixedPlanner(),
        quota=quota,
    )

    task = asyncio.create_task(
        service.process(
            user_message="calculate this",
            user_id=user,
        )
    )

    await asyncio.wait_for(
        started.wait(),
        timeout=1,
    )

    assert quota.active_count(user) == 1

    task.cancel()

    with pytest.raises(asyncio.CancelledError):
        await task

    assert quota.active_count(user) == 0


def test_quota_shared_across_orchestrator_instances():
    runner = NeverCalledRunner()

    service_a = ChatAgentOrchestrator(
        runner=runner,
    )
    service_b = ChatAgentOrchestrator(
        runner=runner,
    )

    assert service_a._quota is service_b._quota
