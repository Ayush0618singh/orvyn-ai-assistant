
"""Real database user isolation and execution audit tests."""

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
    get_audits,
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
async def test_other_user_cannot_execute_approval(environment):
    env = environment

    approval_id = await request_approval(env)

    await decide_approval(env, approval_id)

    with pytest.raises(AgentApprovalExecutionError):
        await execute_approval(
            env,
            approval_id,
            user_id=env["stranger"],
        )

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
async def test_two_users_have_separate_files(environment):
    env = environment

    first_id = await request_approval(
        env,
        user_id=env["owner"],
        content="Owner private data",
    )

    second_id = await request_approval(
        env,
        user_id=env["stranger"],
        content="Stranger private data",
    )

    await decide_approval(
        env,
        first_id,
        user_id=env["owner"],
    )

    await decide_approval(
        env,
        second_id,
        user_id=env["stranger"],
    )

    first = await execute_approval(
        env,
        first_id,
        user_id=env["owner"],
    )

    second = await execute_approval(
        env,
        second_id,
        user_id=env["stranger"],
    )

    assert first.status == ToolExecutionStatus.SUCCEEDED
    assert second.status == ToolExecutionStatus.SUCCEEDED

    assert user_file(
        env,
        env["owner"],
    ).read_text(encoding="utf-8") == "Owner private data"

    assert user_file(
        env,
        env["stranger"],
    ).read_text(encoding="utf-8") == "Stranger private data"


@pytest.mark.asyncio
async def test_successful_execution_is_audited(environment):
    env = environment

    approval_id = await request_approval(env)

    await decide_approval(env, approval_id)

    result = await execute_approval(
        env,
        approval_id,
    )

    assert result.status == ToolExecutionStatus.SUCCEEDED

    audits = await get_audits(
        env,
        approval_id,
    )

    assert len(audits) == 1

    audit = audits[0]

    assert audit.user_id == str(env["owner"])
    assert audit.approval_id == str(approval_id)
    assert audit.tool_name == "workspace_file_write"
    assert audit.status == "succeeded"
    assert audit.completed_at is not None

    # Audit metadata must not contain private file content.
    assert not hasattr(audit, "arguments")
    assert not hasattr(audit, "output")
