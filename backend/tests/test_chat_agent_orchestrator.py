
from uuid import uuid4

import pytest

from app.services.chat_agent_orchestrator import (
    ChatAgentOrchestrator,
)
from app.tools.deterministic_router import (
    DeterministicToolRouter,
)


class FakeExecution:
    def __init__(
        self,
        output,
        tool_name,
    ):
        self.execution_id = uuid4()
        self.tool_name = tool_name
        self.output = output


class FakeSelection:
    def __init__(
        self,
        tool_name,
    ):
        self.tool_name = tool_name


class FakeRunResult:
    def __init__(
        self,
        status,
        tool_name=None,
        output=None,
    ):
        self.status = status
        self.selection = FakeSelection(tool_name)
        self.execution = (
            FakeExecution(
                output=output,
                tool_name=tool_name,
            )
            if output is not None
            else None
        )


class FakeRunner:
    def __init__(
        self,
        result=None,
        error=None,
    ):
        self.result = result
        self.error = error
        self.calls = []

    async def run(self, **kwargs):
        self.calls.append(kwargs)

        if self.error is not None:
            raise self.error

        return self.result


def make_service(
    result=None,
    error=None,
):
    runner = FakeRunner(
        result=result,
        error=error,
    )

    service = ChatAgentOrchestrator(
        runner=runner,
        router=DeterministicToolRouter(),
    )

    return service, runner


@pytest.mark.asyncio
async def test_calculator_request():
    service, runner = make_service(
        FakeRunResult(
            status="succeeded",
            tool_name="calculator",
            output={
                "expression": "25 * 18",
                "result": "450",
            },
        )
    )

    user_id = uuid4()

    decision = await service.process(
        user_message="25 * 18 calculate karo",
        user_id=user_id,
    )

    assert decision.handled is True
    assert decision.status == "succeeded"
    assert decision.response == "25 * 18 = 450"
    assert len(runner.calls) == 1
    assert runner.calls[0]["user_id"] == user_id
    assert runner.calls[0]["granted_permissions"] == []


@pytest.mark.asyncio
async def test_datetime_request():
    service, runner = make_service(
        FakeRunResult(
            status="succeeded",
            tool_name="current_datetime",
            output={
                "timezone": "Asia/Kolkata",
                "date": "2026-10-16",
                "time": "19:14:20",
                "weekday": "Friday",
            },
        )
    )

    decision = await service.process(
        user_message=(
            "India me abhi current time kya hai?"
        ),
        user_id=uuid4(),
    )

    assert decision.handled is True
    assert "Asia/Kolkata" in decision.response
    assert len(runner.calls) == 1


@pytest.mark.asyncio
async def test_normal_chat_skips_tools():
    service, runner = make_service()

    decision = await service.process(
        user_message=(
            "Explain Python decorators"
        ),
        user_id=uuid4(),
    )

    assert decision.handled is False
    assert runner.calls == []


@pytest.mark.asyncio
async def test_attachments_skip_tools():
    service, runner = make_service()

    decision = await service.process(
        user_message="25 * 18 calculate karo",
        user_id=uuid4(),
        has_attachments=True,
    )

    assert decision.handled is False
    assert runner.calls == []


@pytest.mark.asyncio
async def test_documents_skip_tools():
    service, runner = make_service()

    decision = await service.process(
        user_message="25 * 18 calculate karo",
        user_id=uuid4(),
        has_documents=True,
    )

    assert decision.handled is False
    assert runner.calls == []


@pytest.mark.asyncio
async def test_external_context_skips_tools():
    service, runner = make_service()

    decision = await service.process(
        user_message="25 * 18 calculate karo",
        user_id=uuid4(),
        has_external_context=True,
    )

    assert decision.handled is False
    assert runner.calls == []


@pytest.mark.asyncio
async def test_empty_message():
    service, runner = make_service()

    decision = await service.process(
        user_message="   ",
        user_id=uuid4(),
    )

    assert decision.handled is False
    assert runner.calls == []


@pytest.mark.asyncio
async def test_invalid_identity():
    service, _ = make_service()

    with pytest.raises(TypeError):
        await service.process(
            user_message="25 * 18",
            user_id="untrusted-user-id",
        )


@pytest.mark.asyncio
async def test_runner_failure():
    service, runner = make_service(
        error=RuntimeError(
            "Simulated internal failure"
        )
    )

    decision = await service.process(
        user_message="25 * 18 calculate karo",
        user_id=uuid4(),
    )

    assert decision.handled is True
    assert decision.status == "failed"
    assert "Simulated" not in decision.response
    assert len(runner.calls) == 1


@pytest.mark.asyncio
async def test_denied_execution():
    service, _ = make_service(
        FakeRunResult(
            status="denied",
            tool_name="calculator",
        )
    )

    decision = await service.process(
        user_message="25 * 18 calculate karo",
        user_id=uuid4(),
    )

    assert decision.handled is True
    assert decision.status == "denied"
    assert "not permitted" in decision.response


@pytest.mark.asyncio
async def test_no_tool_from_runner():
    service, _ = make_service(
        FakeRunResult(
            status="no_tool",
        )
    )

    decision = await service.process(
        user_message="25 * 18 calculate karo",
        user_id=uuid4(),
    )

    assert decision.handled is False
    assert decision.status == "no_tool"


@pytest.mark.asyncio
async def test_context_ids_are_preserved():
    service, runner = make_service(
        FakeRunResult(
            status="succeeded",
            tool_name="calculator",
            output={
                "expression": "10 / 2",
                "result": "5",
            },
        )
    )

    user_id = uuid4()
    conversation_id = uuid4()
    message_id = uuid4()

    await service.process(
        user_message="What is 10 / 2?",
        user_id=user_id,
        conversation_id=conversation_id,
        message_id=message_id,
    )

    call = runner.calls[0]

    assert call["user_id"] == user_id
    assert call["conversation_id"] == conversation_id
    assert call["message_id"] == message_id
