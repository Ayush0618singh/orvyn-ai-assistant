
"""API regression tests for ORVYN agent plans.

These tests use mocked service boundaries.
No application database is modified.
"""

from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.dependencies import get_current_user
from app.api.v1.routes import agent_plans
from app.db.session import get_db


USER_ID = uuid4()
CONVERSATION_ID = uuid4()
PLAN_ID = uuid4()
STEP_ID = uuid4()


def make_record():
    return SimpleNamespace(
        id=str(PLAN_ID),
        user_id=str(USER_ID),
        conversation_id=str(CONVERSATION_ID),
        original_request="Create Python study notes",
        status="planned",
        created_at=datetime.now(UTC),
    )


def make_step():
    return SimpleNamespace(
        id=str(STEP_ID),
        plan_id=str(PLAN_ID),
        position=0,
        kind="prepare_content",
        description="Prepare a draft response.",
        depends_on=[],
        requires_approval=False,
        status="pending",
    )


def make_client():
    app = FastAPI()
    app.include_router(agent_plans.router)

    async def fake_db():
        yield object()

    async def fake_user():
        return SimpleNamespace(id=str(USER_ID))

    app.dependency_overrides[get_db] = fake_db
    app.dependency_overrides[get_current_user] = (
        fake_user
    )

    return TestClient(app)


def test_create_plan_uses_authenticated_identity(
    monkeypatch,
):
    observed = {}

    async def fake_create(
        db,
        *,
        user_id,
        conversation_id,
        request,
    ):
        observed["user_id"] = user_id
        observed["conversation_id"] = (
            conversation_id
        )
        observed["request"] = request

        return make_record()

    async def fake_steps(db, *, plan_id):
        return [make_step()]

    monkeypatch.setattr(
        agent_plans,
        "create_persistent_plan",
        fake_create,
    )
    monkeypatch.setattr(
        agent_plans,
        "get_plan_steps",
        fake_steps,
    )

    with make_client() as client:
        response = client.post(
            "/agent-plans",
            json={
                "conversation_id": str(
                    CONVERSATION_ID
                ),
                "request": (
                    "Create Python study notes"
                ),
            },
        )

    assert response.status_code == 201
    assert observed["user_id"] == USER_ID
    assert (
        observed["conversation_id"]
        == CONVERSATION_ID
    )
    assert observed["request"] == (
        "Create Python study notes"
    )

    data = response.json()
    assert data["id"] == str(PLAN_ID)
    assert len(data["steps"]) == 1


def test_unknown_conversation_returns_404(
    monkeypatch,
):
    async def fake_create(
        db,
        *,
        user_id,
        conversation_id,
        request,
    ):
        return None

    monkeypatch.setattr(
        agent_plans,
        "create_persistent_plan",
        fake_create,
    )

    with make_client() as client:
        response = client.post(
            "/agent-plans",
            json={
                "conversation_id": str(
                    CONVERSATION_ID
                ),
                "request": "Create study plan",
            },
        )

    assert response.status_code == 404


def test_plan_detail_not_owned_returns_404(
    monkeypatch,
):
    observed = {}

    async def fake_get(
        db,
        *,
        user_id,
        plan_id,
    ):
        observed["user_id"] = user_id
        observed["plan_id"] = plan_id
        return None

    monkeypatch.setattr(
        agent_plans,
        "get_owned_plan",
        fake_get,
    )

    with make_client() as client:
        response = client.get(
            f"/agent-plans/{PLAN_ID}"
        )

    assert response.status_code == 404
    assert observed["user_id"] == USER_ID
    assert observed["plan_id"] == PLAN_ID


def test_list_uses_authenticated_user(
    monkeypatch,
):
    observed = {}

    async def fake_list(
        db,
        *,
        user_id,
        limit,
        offset,
    ):
        observed["user_id"] = user_id
        observed["limit"] = limit
        observed["offset"] = offset

        return [make_record()], 1

    monkeypatch.setattr(
        agent_plans,
        "list_owned_plans",
        fake_list,
    )

    with make_client() as client:
        response = client.get(
            "/agent-plans?limit=10&offset=0"
        )

    assert response.status_code == 200
    assert observed["user_id"] == USER_ID
    assert observed["limit"] == 10
    assert observed["offset"] == 0

    data = response.json()
    assert data["total"] == 1
    assert len(data["items"]) == 1


def test_invalid_conversation_id_returns_422():
    with make_client() as client:
        response = client.post(
            "/agent-plans",
            json={
                "conversation_id": "invalid",
                "request": "Create study plan",
            },
        )

    assert response.status_code == 422


def test_invalid_plan_id_returns_422():
    with make_client() as client:
        response = client.get(
            "/agent-plans/not-a-uuid"
        )

    assert response.status_code == 422


def test_pagination_limit_is_bounded():
    with make_client() as client:
        response = client.get(
            "/agent-plans?limit=1000"
        )

    assert response.status_code == 422
