
"""Ownership and approval-state isolation at HTTP boundary."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from uuid import uuid4

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from app.api.v1.routes.tool_approvals import (
    get_explicit_bearer_user,
    router,
)
from app.db.session import get_db
from app.services.agent_approval_execution_service import (
    AgentApprovalExecutionError,
)


def build_client():
    app = FastAPI()
    app.include_router(router)

    async def fake_user():
        return SimpleNamespace(
            id=str(uuid4()),
            is_active=True,
        )

    async def fake_db():
        yield None

    app.dependency_overrides[
        get_explicit_bearer_user
    ] = fake_user

    app.dependency_overrides[get_db] = fake_db

    return TestClient(app)


def test_unowned_approval_returns_404():
    client = build_client()

    workflow = SimpleNamespace(
        execute_approved=AsyncMock()
    )

    with (
        patch(
            "app.api.v1.routes.tool_approvals."
            "get_owned_approval",
            new_callable=AsyncMock,
        ) as owned,
        patch(
            "app.api.v1.routes.tool_approvals."
            "create_agent_approval_workflow",
            return_value=workflow,
        ),
    ):
        owned.side_effect = HTTPException(
            status_code=404,
            detail="Tool approval not found.",
        )

        response = client.post(
            f"/tool-approvals/{uuid4()}/execute"
        )

    assert response.status_code == 404
    workflow.execute_approved.assert_not_awaited()


def test_nonapproved_request_returns_409():
    client = build_client()

    workflow = SimpleNamespace(
        execute_approved=AsyncMock(
            side_effect=AgentApprovalExecutionError(
                "Approval is not approved."
            )
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
            f"/tool-approvals/{uuid4()}/execute"
        )

    assert response.status_code == 409
