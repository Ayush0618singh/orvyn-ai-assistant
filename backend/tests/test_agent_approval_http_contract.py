
"""Public approval execution API contract tests."""

from fastapi import FastAPI

from app.api.v1.routes.tool_approvals import router


def get_openapi():
    app = FastAPI()
    app.include_router(router)
    return app.openapi()


def test_execution_endpoint_in_openapi():
    schema = get_openapi()

    path = "/tool-approvals/{approval_id}/execute"

    assert path in schema["paths"]
    assert "post" in schema["paths"][path]


def test_execution_has_no_request_body_schema():
    schema = get_openapi()

    operation = schema["paths"][
        "/tool-approvals/{approval_id}/execute"
    ]["post"]

    assert "requestBody" not in operation


def test_execution_has_no_client_permission_parameter():
    schema = get_openapi()

    operation = schema["paths"][
        "/tool-approvals/{approval_id}/execute"
    ]["post"]

    names = {
        parameter["name"]
        for parameter in operation.get("parameters", [])
    }

    assert "granted_permissions" not in names
    assert "user_id" not in names
    assert "tool_name" not in names
    assert "arguments" not in names


def test_execution_response_model_registered():
    schema = get_openapi()

    operation = schema["paths"][
        "/tool-approvals/{approval_id}/execute"
    ]["post"]

    assert "200" in operation["responses"]
    assert "application/json" in (
        operation["responses"]["200"]["content"]
    )
