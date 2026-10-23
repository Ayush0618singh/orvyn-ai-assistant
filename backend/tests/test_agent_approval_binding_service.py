
"""Unit tests for ORVYN agent approval services."""

from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.services.agent_approval_binding_service import (
    AgentApprovalNotFound,
    bind_existing_file_approval,
)
from app.services.agent_approval_query_service import (
    list_owned_agent_approval_links,
)


class FakeDatabase:
    def __init__(self, values):
        self.values = iter(values)
        self.committed = False
        self.rolled_back = False
        self.added = []

    async def scalar(self, statement):
        return next(self.values, None)

    def add(self, value):
        self.added.append(value)

    async def commit(self):
        self.committed = True

    async def rollback(self):
        self.rolled_back = True


@pytest.mark.asyncio
async def test_missing_plan_rejected():
    db = FakeDatabase([None])

    with pytest.raises(
        AgentApprovalNotFound,
        match="Agent plan",
    ):
        await bind_existing_file_approval(
            db,
            user_id=uuid4(),
            plan_id=uuid4(),
            step_id=uuid4(),
            approval_id=uuid4(),
        )

    assert db.rolled_back
    assert not db.committed
    assert not db.added


@pytest.mark.asyncio
async def test_missing_step_rejected():
    user_id = uuid4()
    conversation_id = uuid4()
    plan_id = uuid4()

    plan = SimpleNamespace(
        id=str(plan_id),
        user_id=str(user_id),
        conversation_id=str(conversation_id),
        status="planned",
    )

    db = FakeDatabase([
        plan,
        None,
    ])

    with pytest.raises(
        AgentApprovalNotFound,
        match="Agent step",
    ):
        await bind_existing_file_approval(
            db,
            user_id=user_id,
            plan_id=plan_id,
            step_id=uuid4(),
            approval_id=uuid4(),
        )

    assert db.rolled_back
    assert not db.committed


@pytest.mark.asyncio
async def test_missing_approval_rejected():
    user_id = uuid4()
    conversation_id = uuid4()
    plan_id = uuid4()
    step_id = uuid4()

    plan = SimpleNamespace(
        id=str(plan_id),
        user_id=str(user_id),
        conversation_id=str(conversation_id),
        status="planned",
    )

    step = SimpleNamespace(
        id=str(step_id),
        plan_id=str(plan_id),
        kind="request_file_approval",
        requires_approval=True,
        status="pending",
    )

    db = FakeDatabase([
        plan,
        step,
        None,
    ])

    with pytest.raises(
        AgentApprovalNotFound,
        match="Tool approval",
    ):
        await bind_existing_file_approval(
            db,
            user_id=user_id,
            plan_id=plan_id,
            step_id=step_id,
            approval_id=uuid4(),
        )

    assert db.rolled_back
    assert not db.committed


@pytest.mark.asyncio
async def test_missing_chat_link_rejected():
    user_id = uuid4()
    conversation_id = uuid4()
    plan_id = uuid4()
    step_id = uuid4()
    approval_id = uuid4()

    plan = SimpleNamespace(
        id=str(plan_id),
        user_id=str(user_id),
        conversation_id=str(conversation_id),
        status="planned",
    )

    step = SimpleNamespace(
        id=str(step_id),
        plan_id=str(plan_id),
        kind="request_file_approval",
        requires_approval=True,
        status="pending",
    )

    approval = SimpleNamespace(
        id=str(approval_id),
        user_id=str(user_id),
        tool_name="workspace_file_write",
        status="pending",
    )

    db = FakeDatabase([
        plan,
        step,
        approval,
        None,
    ])

    with pytest.raises(
        AgentApprovalNotFound,
        match="conversation link",
    ):
        await bind_existing_file_approval(
            db,
            user_id=user_id,
            plan_id=plan_id,
            step_id=step_id,
            approval_id=approval_id,
        )

    assert db.rolled_back
    assert not db.committed


@pytest.mark.asyncio
async def test_query_returns_empty_list():
    class EmptyScalars:
        def all(self):
            return []

    class EmptyDatabase:
        async def scalars(self, statement):
            return EmptyScalars()

    result = await list_owned_agent_approval_links(
        EmptyDatabase(),
        user_id=uuid4(),
        plan_id=uuid4(),
    )

    assert result == []


@pytest.mark.asyncio
async def test_query_maps_existing_links():
    user_id = uuid4()
    plan_id = uuid4()
    step_id = uuid4()
    approval_id = uuid4()
    conversation_id = uuid4()

    class Result:
        def all(self):
            return [
                SimpleNamespace(
                    plan_id=str(plan_id),
                    step_id=str(step_id),
                    approval_id=str(approval_id),
                    conversation_id=str(
                        conversation_id
                    ),
                )
            ]

    class Database:
        async def scalars(self, statement):
            return Result()

    result = await list_owned_agent_approval_links(
        Database(),
        user_id=user_id,
        plan_id=plan_id,
    )

    assert len(result) == 1
    assert result[0].plan_id == str(plan_id)
    assert result[0].step_id == str(step_id)
    assert result[0].approval_id == (
        str(approval_id)
    )
