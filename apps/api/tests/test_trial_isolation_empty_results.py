"""Inaccessible trial resources must fail without returning data or performing writes."""
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient

from app.core.auth import AuthContext
from app.core.deps import WorkspaceContext, get_workspace_context
from app.main import app


FOREIGN_ID = "10000000-0000-4000-8000-000000000001"


@pytest.mark.parametrize("result", [None, SimpleNamespace(data=None)])
@pytest.mark.parametrize(
    "method,path,body,expected_status,expected_code,workspace_filter",
    [
        ("PATCH", f"/tasks/{FOREIGN_ID}", {}, 404, "not_found", "workspace_id"),
        ("GET", f"/collaboration/comments?target_type=task&target_id={FOREIGN_ID}",
         None, 404, "not_found", "workspace_id"),
        ("DELETE", f"/collaboration/comments/{FOREIGN_ID}",
         None, 404, "not_found", "workspace_id"),
        ("POST", "/tasks", {"title": "Rejected reference", "project_id": FOREIGN_ID},
         422, "invalid_project", "workspace_id"),
        ("POST", f"/projects/{FOREIGN_ID}/release-plan", {"release_date": "2026-12-01"},
         422, "invalid_project", "workspace_id"),
        ("PATCH", f"/milestones/{FOREIGN_ID}", {},
         404, "not_found", "release_plans.workspace_id"),
        ("PATCH", f"/budgets/{FOREIGN_ID}", {},
         404, "not_found", "workspace_id"),
        ("PATCH", f"/budget-items/{FOREIGN_ID}", {},
         404, "not_found", "budgets.workspace_id"),
        ("PATCH", f"/campaigns/{FOREIGN_ID}", {},
         404, "not_found", "workspace_id"),
        ("PATCH", f"/content/{FOREIGN_ID}", {},
         404, "not_found", "workspace_id"),
        ("PATCH", f"/calendar/events/{FOREIGN_ID}", {},
         404, "not_found", "workspace_id"),
        ("GET", f"/catalogue/{FOREIGN_ID}", None,
         404, "not_found", "workspace_id"),
    ],
)
def test_inaccessible_resources_return_generic_errors_without_writes(
    result, method, path, body, expected_status, expected_code, workspace_filter,
):
    query = Mock()
    for name in ("select", "eq", "maybe_single"):
        getattr(query, name).return_value = query
    query.execute.return_value = result
    db = Mock()
    db.table.return_value = query
    ctx = WorkspaceContext(
        workspace_id="20000000-0000-4000-8000-000000000002",
        role="owner", plan="pro", db=db,
        auth=AuthContext(user_id="second-owner", email="owner@example.com", token="test"),
    )
    app.dependency_overrides[get_workspace_context] = lambda: ctx
    try:
        response = TestClient(app, raise_server_exceptions=False).request(
            method, "/api/v1" + path, json=body,
        )
    finally:
        app.dependency_overrides.pop(get_workspace_context, None)

    assert response.status_code == expected_status
    assert response.json()["error"]["code"] == expected_code
    assert FOREIGN_ID not in response.text
    query.eq.assert_any_call(workspace_filter, ctx.workspace_id)
    for name in ("insert", "update", "delete"):
        getattr(query, name).assert_not_called()
