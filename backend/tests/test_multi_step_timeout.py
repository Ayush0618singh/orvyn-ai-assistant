
"""ORVYN Phase 10J-E1 timeout and cancellation tests."""

import asyncio
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.tools.multi_step_engine import (
    ArithmeticPlan,
    SecureMultiStepEngine,
    Step,
)


def make_plan():
    return ArithmeticPlan(
        steps=[
            Step(
                id="first",
                expression="10 * 5",
            ),
            Step(
                id="second",
                expression="$first * 2",
            ),
        ]
    )


class FastRunner:
    def __init__(self):
        self.calls = []

    async def run(self, **kwargs):
        self.calls.append(kwargs)

        expression = kwargs["user_message"].removesuffix(
            " calculate karo"
        )

        results = {
            "10 * 5": "50",
            "(50) * 2": "100",
        }

        return SimpleNamespace(
            status="succeeded",
            selection=SimpleNamespace(
                tool_name="calculator"
            ),
            execution=SimpleNamespace(
                tool_name="calculator",
                execution_id=uuid4(),
                output={
                    "expression": expression,
                    "result": results[expression],
                },
            ),
        )


class SlowRunner:
    def __init__(self):
        self.calls = 0
        self.cancelled = False

    async def run(self, **kwargs):
        self.calls += 1

        try:
            await asyncio.sleep(10)
        except asyncio.CancelledError:
            self.cancelled = True
            raise


class SlowSecondStepRunner(FastRunner):
    def __init__(self):
        super().__init__()
        self.cancelled = False

    async def run(self, **kwargs):
        if len(self.calls) == 1:
            self.calls.append(kwargs)

            try:
                await asyncio.sleep(10)
            except asyncio.CancelledError:
                self.cancelled = True
                raise

        return await super().run(**kwargs)


@pytest.mark.asyncio
async def test_fast_plan_succeeds():
    runner = FastRunner()

    engine = SecureMultiStepEngine(
        runner,
        timeout_seconds=1,
    )

    result = await engine.execute(
        plan=make_plan(),
        user_id=uuid4(),
    )

    assert result.status == "succeeded"
    assert result.final_result == "100"
    assert len(result.records) == 2
    assert len(runner.calls) == 2


@pytest.mark.asyncio
async def test_slow_step_times_out():
    runner = SlowRunner()

    engine = SecureMultiStepEngine(
        runner,
        timeout_seconds=0.02,
    )

    result = await engine.execute(
        plan=make_plan(),
        user_id=uuid4(),
    )

    assert result.status == "failed"
    assert result.final_result is None
    assert "time limit" in result.message
    assert runner.calls == 1
    assert runner.cancelled is True


@pytest.mark.asyncio
async def test_timeout_preserves_completed_records():
    runner = SlowSecondStepRunner()

    engine = SecureMultiStepEngine(
        runner,
        timeout_seconds=0.02,
    )

    result = await engine.execute(
        plan=make_plan(),
        user_id=uuid4(),
    )

    assert result.status == "failed"
    assert result.final_result is None
    assert len(result.records) == 1
    assert result.records[0].result == "50"
    assert runner.cancelled is True


@pytest.mark.asyncio
async def test_external_cancellation_propagates():
    runner = SlowRunner()

    engine = SecureMultiStepEngine(
        runner,
        timeout_seconds=5,
    )

    task = asyncio.create_task(
        engine.execute(
            plan=make_plan(),
            user_id=uuid4(),
        )
    )

    await asyncio.sleep(0.02)
    task.cancel()

    with pytest.raises(asyncio.CancelledError):
        await task

    assert runner.cancelled is True


@pytest.mark.parametrize(
    "timeout",
    [
        0,
        -1,
        31,
        float("nan"),
        float("inf"),
        float("-inf"),
        True,
        "invalid",
    ],
)
def test_invalid_timeout_rejected(timeout):
    with pytest.raises(ValueError):
        SecureMultiStepEngine(
            FastRunner(),
            timeout_seconds=timeout,
        )


@pytest.mark.asyncio
async def test_timeout_does_not_grant_permissions():
    runner = FastRunner()

    engine = SecureMultiStepEngine(
        runner,
        timeout_seconds=1,
    )

    user_id = uuid4()

    result = await engine.execute(
        plan=make_plan(),
        user_id=user_id,
    )

    assert result.status == "succeeded"

    for call in runner.calls:
        assert call["user_id"] == user_id
        assert call["granted_permissions"] == []


@pytest.mark.asyncio
async def test_invalid_forward_reference_rejected_before_execution():
    runner = FastRunner()

    engine = SecureMultiStepEngine(
        runner,
        timeout_seconds=1,
    )

    plan = ArithmeticPlan(
        steps=[
            Step(
                id="first",
                expression="$second * 2",
            ),
            Step(
                id="second",
                expression="10 * 5",
            ),
        ]
    )

    with pytest.raises(ValueError):
        await engine.execute(
            plan=plan,
            user_id=uuid4(),
        )

    assert runner.calls == []
