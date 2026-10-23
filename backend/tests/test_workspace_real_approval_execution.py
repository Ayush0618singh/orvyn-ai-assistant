
"""Real database-backed workspace execution tests."""

import pytest

from app.tools.enums import ToolExecutionStatus

from tests.workspace_e2e_support import (
    create_environment,
    decide_approval,
    execute_approval,
    get_approval,
    request_approval,
    user_file,
)


@pytest.fixture
async def environment(tmp_path, monkeypatch):
    env = await create_environment(
        tmp_path,
        monkeypatch,
    )

    try:
        yield env
    finally:
        await env["engine"].dispose()


@pytest.mark.asyncio
async def test_pending_approval_is_persisted(environment):
    env = environment

    approval_id = await request_approval(env)

    record = await get_approval(
        env,
        approval_id,
    )

    assert record.status == "pending"
    assert record.tool_name == "workspace_file_write"
    assert record.user_id == str(env["owner"])

    assert not user_file(
        env,
        env["owner"],
    ).exists()


@pytest.mark.asyncio
async def test_approved_file_creation(environment):
    env = environment

    approval_id = await request_approval(
        env,
        content="ORVYN real database test",
    )

    await decide_approval(
        env,
        approval_id,
    )

    result = await execute_approval(
        env,
        approval_id,
    )

    assert result.status == ToolExecutionStatus.SUCCEEDED
    assert result.output["status"] == "created"

    saved = user_file(
        env,
        env["owner"],
    )

    assert saved.is_file()
    assert saved.read_text(
        encoding="utf-8"
    ) == "ORVYN real database test"

    record = await get_approval(
        env,
        approval_id,
    )

    assert record.status == "consumed"


@pytest.mark.asyncio
async def test_pending_request_cannot_execute(environment):
    from app.services.agent_approval_execution_service import (
        AgentApprovalExecutionError,
    )

    env = environment

    approval_id = await request_approval(env)

    with pytest.raises(AgentApprovalExecutionError):
        await execute_approval(
            env,
            approval_id,
        )

    assert not user_file(
        env,
        env["owner"],
    ).exists()


@pytest.mark.asyncio
async def test_denied_request_cannot_execute(environment):
    from app.services.agent_approval_execution_service import (
        AgentApprovalExecutionError,
    )

    env = environment

    approval_id = await request_approval(env)

    await decide_approval(
        env,
        approval_id,
        approve=False,
    )

    with pytest.raises(AgentApprovalExecutionError):
        await execute_approval(
            env,
            approval_id,
        )

    assert not user_file(
        env,
        env["owner"],
    ).exists()
