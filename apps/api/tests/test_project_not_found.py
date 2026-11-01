"""Missing and RLS-hidden projects must return 404 without a server error."""
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient

from app.core.auth import AuthContext
from app.core.deps import WorkspaceContext, get_workspace_context
from app.main import app


@pytest.mark.parametrize("result", [None, SimpleNamespace(data=None)])
def test_hidden_project_returns_404_for_both_empty_database_response_shapes(result):
    query = Mock()
    for method in ("select", "eq", "maybe_single"):
        getattr(query, method).return_value = query
    query.execute.return_value = result
    db = Mock()
    db.table.return_value = query
    ctx = WorkspaceContext(
        workspace_id="second-owner-workspace", role="owner", plan="free", db=db,
        auth=AuthContext(user_id="second-owner", email="owner@example.com", token="test"),
    )
    app.dependency_overrides[get_workspace_context] = lambda: ctx
    try:
        response = TestClient(app).get("/api/v1/projects/other-owner-project")
    finally:
        app.dependency_overrides.pop(get_workspace_context, None)

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"
    query.eq.assert_any_call("workspace_id", ctx.workspace_id)
