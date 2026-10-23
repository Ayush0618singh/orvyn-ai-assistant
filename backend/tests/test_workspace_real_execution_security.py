
"""Database-backed replay and permission security tests."""

import pytest

from app.services.agent_approval_execution_service import (
    AgentApprovalExecutionError,
)
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
async def test_replay_cannot_execute_twice(environment):
    env = environment

    approval_id = await request_approval(env)

    await decide_approval(env, approval_id)

    first = await execute_approval(
        env,
        approval_id,
    )

    assert first.status == ToolExecutionStatus.SUCCEEDED

    with pytest.raises(AgentApprovalExecutionError):
        await execute_approval(
            env,
            approval_id,
        )

    assert user_file(
        env,
        env["owner"],
    ).read_text(encoding="utf-8") == "Hello ORVYN"


@pytest.mark.asyncio
async def test_missing_permission_blocks_execution(environment):
    env = environment

    approval_id = await request_approval(env)

    await decide_approval(env, approval_id)

    result = await execute_approval(
        env,
        approval_id,
        permitted=False,
    )

    assert result.status == ToolExecutionStatus.DENIED
    assert result.error.code == "PERMISSION_DENIED"

    record = await get_approval(
        env,
        approval_id,
    )

    assert record.status == "approved"

    assert not user_file(
        env,
        env["owner"],
    ).exists()


@pytest.mark.asyncio
async def test_existing_file_is_not_overwritten(environment):
    env = environment

    first_id = await request_approval(
        env,
        content="Original content",
    )

    await decide_approval(env, first_id)

    first = await execute_approval(
        env,
        first_id,
    )

    assert first.status == ToolExecutionStatus.SUCCEEDED

    second_id = await request_approval(
        env,
        content="Replacement content",
    )

    await decide_approval(env, second_id)

    second = await execute_approval(
        env,
        second_id,
    )

    assert second.status == ToolExecutionStatus.FAILED

    saved = user_file(
        env,
        env["owner"],
    )

    assert saved.read_text(
        encoding="utf-8"
    ) == "Original content"
