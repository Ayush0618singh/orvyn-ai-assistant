from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.api.v1.routes import chat as chat_route


class FakeOrchestrator:
    def __init__(self, *, handled=True, response='10 / 2 = 5', tool_name='calculator'):
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


def arguments(**overrides):
    params = dict(
        request=SimpleNamespace(message='What is 10 / 2?'),
        current_user=SimpleNamespace(id=str(uuid4())),
        conversation=SimpleNamespace(id=str(uuid4())),
        user_message=SimpleNamespace(id=str(uuid4())),
        attachments=[],
        active_document_ids=[],
        rag_sources=[],
        web_response_sources=[],
        memory_command_response=None,
        web_guard_response=None,
    )
    params.update(overrides)
    return params


@pytest.mark.asyncio
async def test_tool_result_uses_trusted_identity(monkeypatch):
    fake = FakeOrchestrator()
    monkeypatch.setattr(chat_route, 'create_chat_agent_orchestrator', lambda: fake)
    params = arguments()
    response, name = await chat_route.resolve_chat_tool_response(**params)
    assert (response, name) == ('10 / 2 = 5', 'calculator')
    assert fake.calls[0]['user_id'] == uuid4_from(params['current_user'].id)
    assert fake.calls[0]['conversation_id'] == uuid4_from(params['conversation'].id)
    assert fake.calls[0]['message_id'] == uuid4_from(params['user_message'].id)


def uuid4_from(value):
    from uuid import UUID
    return UUID(str(value))


@pytest.mark.asyncio
@pytest.mark.parametrize('override', [
    {'memory_command_response': 'Memory saved'},
    {'web_guard_response': 'Live verification unavailable'},
    {'request': SimpleNamespace(message='')},
])
async def test_guards_do_not_call_agent(monkeypatch, override):
    def unexpected():
        raise AssertionError('Tool runner must not be constructed')
    monkeypatch.setattr(chat_route, 'create_chat_agent_orchestrator', unexpected)
    assert await chat_route.resolve_chat_tool_response(**arguments(**override)) == (None, None)


@pytest.mark.asyncio
async def test_documents_skip_execution(monkeypatch):
    fake = FakeOrchestrator(handled=False, response=None)
    monkeypatch.setattr(chat_route, 'create_chat_agent_orchestrator', lambda: fake)
    result = await chat_route.resolve_chat_tool_response(
        **arguments(active_document_ids=['document-1'])
    )
    assert result == (None, None)
    assert fake.calls[0]['has_documents'] is True


@pytest.mark.asyncio
async def test_tool_not_handled(monkeypatch):
    fake = FakeOrchestrator(handled=False, response=None)
    monkeypatch.setattr(chat_route, 'create_chat_agent_orchestrator', lambda: fake)
    assert await chat_route.resolve_chat_tool_response(**arguments()) == (None, None)
