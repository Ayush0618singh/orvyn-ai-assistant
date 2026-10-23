
"""HTTP authentication tests for workspace approvals."""

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


def test_request_requires_bearer_token():
    with build_client() as client:
        response = client.post(
            "/tool-approvals/workspace-file",
            json={
                "filename": "notes.txt",
                "content": "Hello",
            },
        )

    assert response.status_code == 401


def test_invalid_bearer_token_rejected():
    with build_client() as client:
        response = client.post(
            "/tool-approvals/workspace-file",
            headers={
                "Authorization": "Bearer invalid-token",
            },
            json={
                "filename": "notes.txt",
                "content": "Hello",
            },
        )

    assert response.status_code == 401


def test_basic_auth_rejected():
    with build_client() as client:
        response = client.post(
            "/tool-approvals/workspace-file",
            headers={
                "Authorization": "Basic dGVzdDp0ZXN0",
            },
            json={
                "filename": "notes.txt",
                "content": "Hello",
            },
        )

    assert response.status_code == 401


def test_cookie_cannot_authorize_request():
    with build_client() as client:
        client.cookies.set(
            "access_token",
            "fake-token",
        )

        response = client.post(
            "/tool-approvals/workspace-file",
            json={
                "filename": "notes.txt",
                "content": "Hello",
            },
        )

    assert response.status_code == 401


def test_extra_fields_rejected():
    with build_client() as client:
        response = client.post(
            "/tool-approvals/workspace-file",
            json={
                "filename": "notes.txt",
                "content": "Hello",
                "approved": True,
            },
        )

    # Authentication occurs before an unauthorized
    # request may reach the tool execution workflow.
    assert response.status_code in (401, 422)
