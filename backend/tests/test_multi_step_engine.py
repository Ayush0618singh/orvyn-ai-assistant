from types import SimpleNamespace
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.tools.multi_step_engine import ArithmeticPlan, SecureMultiStepEngine


class FakeRunner:
    def __init__(self, fail_at=None):
        self.calls = []
        self.fail_at = fail_at

    async def run(self, **kwargs):
        self.calls.append(kwargs)
        if len(self.calls) == self.fail_at:
            return SimpleNamespace(status="denied", execution=None, selection=SimpleNamespace(tool_name="calculator"))
        expression = kwargs["user_message"].removesuffix(" calculate karo")
        # Fake runner is for orchestration tests only, never production execution.
        results = {"2500 * 18": "45000", "(45000) * 12 / 100": "5400"}
        return SimpleNamespace(
            status="succeeded",
            selection=SimpleNamespace(tool_name="calculator"),
            execution=SimpleNamespace(
                tool_name="calculator", execution_id=uuid4(),
                output={"expression": expression, "result": results[expression]},
            ),
        )


def plan():
    return ArithmeticPlan(steps=[
        {"id": "total", "expression": "2500 * 18"},
        {"id": "percent", "expression": "$total * 12 / 100"},
    ])


@pytest.mark.asyncio
async def test_sequential_execution_and_trusted_identity():
    runner = FakeRunner()
    user_id, conversation_id, message_id = uuid4(), uuid4(), uuid4()
    result = await SecureMultiStepEngine(runner).execute(
        plan=plan(), user_id=user_id,
        conversation_id=conversation_id, message_id=message_id,
    )
    assert result.status == "succeeded"
    assert result.final_result == "5400"
    assert len(result.records) == 2
    assert all(c["user_id"] == user_id and c["granted_permissions"] == [] for c in runner.calls)
    assert all(c["conversation_id"] == conversation_id and c["message_id"] == message_id for c in runner.calls)


@pytest.mark.asyncio
async def test_failure_stops_subsequent_steps():
    runner = FakeRunner(fail_at=1)
    result = await SecureMultiStepEngine(runner).execute(plan=plan(), user_id=uuid4())
    assert result.status == "failed"
    assert result.final_result is None
    assert len(runner.calls) == 1


@pytest.mark.asyncio
async def test_forward_reference_rejected_before_execution():
    runner = FakeRunner()
    with pytest.raises(ValueError):
        await SecureMultiStepEngine(runner).execute(
            plan=ArithmeticPlan(steps=[{"id": "first", "expression": "$later + 1"},
                                       {"id": "later", "expression": "2 + 2"}]),
            user_id=uuid4(),
        )
    assert runner.calls == []


def test_invalid_plan_rejected():
    with pytest.raises(ValidationError):
        ArithmeticPlan(steps=[{"id": "x", "expression": "1+1"}] * 6)
    with pytest.raises(ValidationError):
        ArithmeticPlan(steps=[{"id": "x", "expression": "1+1"}, {"id": "x", "expression": "2+2"}])
    with pytest.raises(ValidationError):
        ArithmeticPlan(steps=[{"id": "x", "expression": "1+1", "permissions": ["system.write"]}])


@pytest.mark.asyncio
async def test_non_arithmetic_input_rejected_before_execution():
    runner = FakeRunner()
    with pytest.raises(ValueError):
        await SecureMultiStepEngine(runner).execute(
            plan=ArithmeticPlan(steps=[{"id": "x", "expression": "__import__('os')"}]),
            user_id=uuid4(),
        )
    assert runner.calls == []


@pytest.mark.asyncio
async def test_invalid_identity_rejected():
    with pytest.raises(TypeError):
        await SecureMultiStepEngine(FakeRunner()).execute(plan=plan(), user_id="untrusted")
