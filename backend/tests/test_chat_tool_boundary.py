
"""ORVYN Phase 10K-E1: Chat tool security boundary tests.

Tests the bridge between authenticated chat context and
the existing agent orchestrator without live API calls.
"""

from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest

from app.api.v1.routes import chat as chat_route


class RecordingOrchestrator:
    """Records agent requests without executing real tools."""

    def __init__(
        self,
        *,
        handled=True,
        response="Text analysis completed:\nWords: 4",
        tool_name="text_analyzer",
    ):
        self.handled = handled
        self.response = response
        self.tool_name = tool_name
        self.calls = []

    async def process(self, **kwargs):
        self.calls.append(kwargs)

        return SimpleNamespace(
            handled=self.handled,
            response=self.response,
            tool_name=self.tool_name,
        )


def make_context(**overrides):
    """Create isolated, synthetic authenticated chat context."""

    context = {
        "request": SimpleNamespace(
            message='Count the words in "Hello world from ORVYN"'
        ),
        "current_user": SimpleNamespace(
            id=str(uuid4())
        ),
        "conversation": SimpleNamespace(
            id=str(uuid4())
        ),
        "user_message": SimpleNamespace(
            id=str(uuid4())
        ),
        "attachments": [],
        "active_document_ids": [],
        "rag_sources": [],
        "web_response_sources": [],
        "memory_command_response": None,
        "web_guard_response": None,
    }

    context.update(overrides)
    return context


@pytest.mark.asyncio
async def test_authenticated_identity_is_forwarded(
    monkeypatch,
):
    agent = RecordingOrchestrator()

    monkeypatch.setattr(
        chat_route,
        "create_chat_agent_orchestrator",
        lambda: agent,
    )

    context = make_context()

    response, tool_name = (
        await chat_route.resolve_chat_tool_response(
            **context
        )
    )

    assert tool_name == "text_analyzer"
    assert "Words: 4" in response

    assert len(agent.calls) == 1

    call = agent.calls[0]

    assert call["user_id"] == UUID(
        context["current_user"].id
    )

    assert call["conversation_id"] == UUID(
        context["conversation"].id
    )

    assert call["message_id"] == UUID(
        context["user_message"].id
    )

    assert call["user_message"] == (
        context["request"].message
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "blocked_context",
    [
        {
            "memory_command_response":
                "Memory command handled"
        },
        {
            "web_guard_response":
                "Live verification unavailable"
        },
        {
            "request":
                SimpleNamespace(message="")
        },
    ],
)
async def test_precedence_guards_prevent_agent_creation(
    monkeypatch,
    blocked_context,
):
    def forbidden_factory():
        raise AssertionError(
            "Agent must not be created for guarded requests."
        )

    monkeypatch.setattr(
        chat_route,
        "create_chat_agent_orchestrator",
        forbidden_factory,
    )

    context = make_context(
        **blocked_context
    )

    result = (
        await chat_route.resolve_chat_tool_response(
            **context
        )
    )

    assert result == (None, None)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "context_name,context_value,expected_flag",
    [
        (
            "attachments",
            [SimpleNamespace(id="attachment-1")],
            "has_attachments",
        ),
        (
            "active_document_ids",
            ["document-1"],
            "has_documents",
        ),
        (
            "rag_sources",
            [{"chunk_id": "chunk-1"}],
            "has_documents",
        ),
        (
            "web_response_sources",
            [{"title": "External source"}],
            "has_external_context",
        ),
    ],
)
async def test_external_context_flags_forwarded(
    monkeypatch,
    context_name,
    context_value,
    expected_flag,
):
    agent = RecordingOrchestrator(
        handled=False,
        response=None,
    )

    monkeypatch.setattr(
        chat_route,
        "create_chat_agent_orchestrator",
        lambda: agent,
    )

    context = make_context(
        **{context_name: context_value}
    )

    result = (
        await chat_route.resolve_chat_tool_response(
            **context
        )
    )

    assert result == (None, None)
    assert len(agent.calls) == 1
    assert agent.calls[0][expected_flag] is True


@pytest.mark.asyncio
async def test_unhandled_request_falls_back_to_chat(
    monkeypatch,
):
    agent = RecordingOrchestrator(
        handled=False,
        response=None,
    )

    monkeypatch.setattr(
        chat_route,
        "create_chat_agent_orchestrator",
        lambda: agent,
    )

    result = (
        await chat_route.resolve_chat_tool_response(
            **make_context()
        )
    )

    assert result == (None, None)
    assert len(agent.calls) == 1


@pytest.mark.asyncio
async def test_empty_handled_response_fails_closed(
    monkeypatch,
):
    agent = RecordingOrchestrator(
        handled=True,
        response="",
    )

    monkeypatch.setattr(
        chat_route,
        "create_chat_agent_orchestrator",
        lambda: agent,
    )

    with pytest.raises(
        RuntimeError,
        match="no safe response",
    ):
        await chat_route.resolve_chat_tool_response(
            **make_context()
        )


@pytest.mark.asyncio
async def test_untrusted_user_uuid_is_rejected(
    monkeypatch,
):
    agent = RecordingOrchestrator()

    monkeypatch.setattr(
        chat_route,
        "create_chat_agent_orchestrator",
        lambda: agent,
    )

    context = make_context(
        current_user=SimpleNamespace(
            id="not-a-valid-uuid"
        )
    )

    with pytest.raises(ValueError):
        await chat_route.resolve_chat_tool_response(
            **context
        )

    assert agent.calls == []


@pytest.mark.asyncio
async def test_untrusted_conversation_uuid_is_rejected(
    monkeypatch,
):
    agent = RecordingOrchestrator()

    monkeypatch.setattr(
        chat_route,
        "create_chat_agent_orchestrator",
        lambda: agent,
    )

    context = make_context(
        conversation=SimpleNamespace(
            id="invalid-conversation-id"
        )
    )

    with pytest.raises(ValueError):
        await chat_route.resolve_chat_tool_response(
            **context
        )

    assert agent.calls == []
