
"""Approval execution route security contract tests."""

from fastapi.routing import APIRoute

from app.api.v1.routes.tool_approvals import router


def find_execution_route():
    matches = [
        route
        for route in router.routes
        if isinstance(route, APIRoute)
        and route.path == "/tool-approvals/{approval_id}/execute"
    ]

    assert len(matches) == 1
    return matches[0]


def test_execution_endpoint_uses_post():
    route = find_execution_route()

    assert route.methods == {"POST"}


def test_execution_endpoint_has_no_request_body():
    route = find_execution_route()

    assert route.body_field is None


def test_execution_endpoint_returns_tool_result():
    route = find_execution_route()

    assert route.response_model.__name__ == (
        "ToolExecutionResult"
    )


def test_execution_endpoint_requires_bearer_dependency():
    route = find_execution_route()

    dependency_names = {
        dependency.call.__name__
        for dependency in route.dependant.dependencies
    }

    assert "get_explicit_bearer_user" in dependency_names
