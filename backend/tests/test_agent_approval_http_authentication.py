
"""HTTP authentication boundaries for approval execution."""

from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.v1.routes.tool_approvals import router
from app.db.session import get_db


def build_client():
    app = FastAPI()
    app.include_router(router)

    async def fake_db():
        yield None

    app.dependency_overrides[get_db] = fake_db

    return TestClient(app)


def test_execute_requires_bearer_token():
    client = build_client()

    response = client.post(
        f"/tool-approvals/{uuid4()}/execute"
    )

    assert response.status_code == 401


def test_cookie_does_not_authorize_execution():
    client = build_client()

    response = client.post(
        f"/tool-approvals/{uuid4()}/execute",
        cookies={
            "access_token": "fake-token",
        },
    )

    assert response.status_code == 401


def test_invalid_bearer_token_is_rejected():
    client = build_client()

    response = client.post(
        f"/tool-approvals/{uuid4()}/execute",
        headers={
            "Authorization": "Bearer invalid-token",
        },
    )

    assert response.status_code == 401


def test_basic_auth_cannot_execute():
    client = build_client()

    response = client.post(
        f"/tool-approvals/{uuid4()}/execute",
        headers={
            "Authorization": "Basic dGVzdDp0ZXN0",
        },
    )

    assert response.status_code == 401
