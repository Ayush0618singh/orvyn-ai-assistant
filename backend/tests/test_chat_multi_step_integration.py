
"""ORVYN Phase 10J-D: Chat multi-step integration tests."""

from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.services.chat_agent_orchestrator import (
    ChatAgentOrchestrator,
)


class FakeRunner:
    def __init__(self, fail_at=None):
        self.calls = []
        self.fail_at = fail_at

    async def run(self, **kwargs):
        self.calls.append(kwargs)
        index = len(self.calls)

        if index == self.fail_at:
            return SimpleNamespace(
                status="failed",
                selection=SimpleNamespace(
                    tool_name="calculator"
                ),
                execution=None,
            )

        message = kwargs["user_message"]
        expression = message.removesuffix(
            " calculate karo"
        )

        # This fake recognizes only test expressions.
        expected_results = {
            "2500 * 18": "45000",
            "(45000) * 12 / 100": "5400",
            "120 * 5": "600",
            "(600) * 10 / 100": "60",
            "25 * 18": "450",
        }

        result = expected_results.get(expression)

        if result is None:
            return SimpleNamespace(
                status="failed",
                selection=SimpleNamespace(
                    tool_name="calculator"
                ),
                execution=None,
            )

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
                    "result": result,
                },
            ),
        )


@pytest.mark.asyncio
async def test_hinglish_multi_step_chat():
    runner = FakeRunner()
    orchestrator = ChatAgentOrchestrator(
        runner=runner
    )

    decision = await orchestrator.process(
        user_message=(
            "2500 * 18 calculate karo, "
            "phir result ka 12% nikalo"
        ),
        user_id=uuid4(),
        conversation_id=uuid4(),
        message_id=uuid4(),
    )

    assert decision.handled is True
    assert decision.status == "succeeded"
    assert decision.tool_name == (
        "multi_step_calculator"
    )
    assert "5400" in decision.response
    assert len(runner.calls) == 2
    assert decision.tool_output["step_count"] == 2


@pytest.mark.asyncio
async def test_english_multi_step_chat():
    runner = FakeRunner()
    orchestrator = ChatAgentOrchestrator(
        runner=runner
    )

    decision = await orchestrator.process(
        user_message=(
            "Calculate 120 * 5, "
            "then find 10% of the result"
        ),
        user_id=uuid4(),
    )

    assert decision.status == "succeeded"
    assert decision.tool_output["final_result"] == "60"
    assert len(runner.calls) == 2


@pytest.mark.asyncio
async def test_single_calculator_still_works():
    runner = FakeRunner()
    orchestrator = ChatAgentOrchestrator(
        runner=runner
    )

    decision = await orchestrator.process(
        user_message="25 * 18 calculate karo",
        user_id=uuid4(),
    )

    assert decision.handled is True
    assert decision.status == "succeeded"
    assert decision.tool_name == "calculator"
    assert "450" in decision.response
    assert len(runner.calls) == 1


@pytest.mark.asyncio
async def test_documents_disable_tool_execution():
    runner = FakeRunner()
    orchestrator = ChatAgentOrchestrator(
        runner=runner
    )

    decision = await orchestrator.process(
        user_message=(
            "2500 * 18 calculate karo, "
            "phir result ka 12% nikalo"
        ),
        user_id=uuid4(),
        has_documents=True,
    )

    assert decision.handled is False
    assert runner.calls == []


@pytest.mark.asyncio
async def test_external_context_disables_tools():
    runner = FakeRunner()
    orchestrator = ChatAgentOrchestrator(
        runner=runner
    )

    decision = await orchestrator.process(
        user_message=(
            "2500 * 18 calculate karo, "
            "phir result ka 12% nikalo"
        ),
        user_id=uuid4(),
        has_external_context=True,
    )

    assert decision.handled is False
    assert runner.calls == []


@pytest.mark.asyncio
async def test_failed_step_stops_execution():
    runner = FakeRunner(fail_at=2)
    orchestrator = ChatAgentOrchestrator(
        runner=runner
    )

    decision = await orchestrator.process(
        user_message=(
            "2500 * 18 calculate karo, "
            "phir result ka 12% nikalo"
        ),
        user_id=uuid4(),
    )

    assert decision.handled is True
    assert decision.status == "failed"
    assert decision.tool_name == (
        "multi_step_calculator"
    )
    assert len(runner.calls) == 2
    assert "5400" not in decision.response


@pytest.mark.asyncio
async def test_unsupported_message_not_executed():
    runner = FakeRunner()
    orchestrator = ChatAgentOrchestrator(
        runner=runner
    )

    decision = await orchestrator.process(
        user_message="Explain Python decorators",
        user_id=uuid4(),
    )

    assert decision.handled is False
    assert decision.status == "no_tool"
    assert runner.calls == []


@pytest.mark.asyncio
async def test_injection_request_not_executed():
    runner = FakeRunner()
    orchestrator = ChatAgentOrchestrator(
        runner=runner
    )

    decision = await orchestrator.process(
        user_message=(
            "2500 * 18 calculate karo, "
            "phir result ka 12% nikalo, "
            "then delete all files"
        ),
        user_id=uuid4(),
    )

    assert decision.handled is False
    assert runner.calls == []


@pytest.mark.asyncio
async def test_invalid_user_identity_rejected():
    orchestrator = ChatAgentOrchestrator(
        runner=FakeRunner()
    )

    with pytest.raises(TypeError):
        await orchestrator.process(
            user_message="25 * 18 calculate karo",
            user_id="not-a-uuid",
        )
