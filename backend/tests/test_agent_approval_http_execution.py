
"""HTTP-level tests for approved tool execution."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.v1.routes.tool_approvals import (
    get_explicit_bearer_user,
    router,
)
from app.db.session import get_db
from app.schemas.tool import ToolExecutionResult
from app.tools.enums import ToolExecutionStatus


def build_client():
    app = FastAPI()
    app.include_router(router)

    user_id = uuid4()

    async def fake_user():
        return SimpleNamespace(
            id=str(user_id),
            is_active=True,
        )

    async def fake_db():
        yield object()

    app.dependency_overrides[
        get_explicit_bearer_user
    ] = fake_user

    app.dependency_overrides[get_db] = fake_db

    return TestClient(app), user_id


def test_approved_execution_http_success():
    client, user_id = build_client()

    approval_id = uuid4()
    execution_id = uuid4()

    expected = ToolExecutionResult(
        execution_id=execution_id,
        tool_name="test_action",
        status=ToolExecutionStatus.SUCCEEDED,
        output={"completed": True},
    )

    workflow = SimpleNamespace(
        execute_approved=AsyncMock(
            return_value=expected
        )
    )

    with (
        patch(
            "app.api.v1.routes.tool_approvals."
            "get_owned_approval",
            new_callable=AsyncMock,
        ),
        patch(
            "app.api.v1.routes.tool_approvals."
            "create_agent_approval_workflow",
            return_value=workflow,
        ),
    ):
        response = client.post(
            f"/tool-approvals/{approval_id}/execute"
        )

    assert response.status_code == 200

    body = response.json()

    assert body["execution_id"] == str(execution_id)
    assert body["tool_name"] == "test_action"
    assert body["status"] == ToolExecutionStatus.SUCCEEDED.value
    assert body["output"] == {"completed": True}

    kwargs = workflow.execute_approved.await_args.kwargs

    assert kwargs["user_id"] == user_id
    assert kwargs["approval_id"] == approval_id
    assert kwargs["granted_permissions"] == []


def test_invalid_approval_id_http_404():
    client, _ = build_client()

    response = client.post(
        "/tool-approvals/not-a-uuid/execute"
    )

    assert response.status_code == 404


def test_execution_is_post_only():
    client, _ = build_client()

    response = client.get(
        f"/tool-approvals/{uuid4()}/execute"
    )

    assert response.status_code == 405
