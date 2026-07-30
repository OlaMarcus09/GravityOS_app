"""Skeleton smoke tests: app imports, health works, route table is complete,
and protected routes reject unauthenticated calls."""
from __future__ import annotations

import os

# Minimal env so Settings() constructs without a real project.
os.environ.setdefault("SUPABASE_URL", "https://example.supabase.co")
os.environ.setdefault("SUPABASE_ANON_KEY", "test-anon")
os.environ.setdefault("SUPABASE_SERVICE_ROLE_KEY", "test-service")
os.environ.setdefault("SUPABASE_JWT_SECRET", "test-secret")

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402

client = TestClient(app)


def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_me_requires_auth():
    # No bearer token → 401 from HTTPBearer.
    r = client.get("/api/v1/me")
    assert r.status_code == 401
    assert r.json() == {
        "error": {
            "code": "http_error",
            "message": "Not authenticated",
            "details": None,
        }
    }


def test_expected_routes_registered():
    paths = set(app.openapi()["paths"].keys())
    expected = {
        "/api/v1/me",
        "/api/v1/workspaces",
        "/api/v1/projects",
        "/api/v1/tasks",
        "/api/v1/calendar",
        "/api/v1/catalogue",
        "/api/v1/budgets",
        "/api/v1/campaigns",
        "/api/v1/dashboard",
        "/api/v1/gravity-score",
        "/api/v1/ai/outputs",
    }
    missing = expected - paths
    assert not missing, f"missing routes: {missing}"


def test_validation_errors_use_public_error_contract():
    from app.core.auth import AuthContext, get_auth_context
    from app.core.deps import WorkspaceContext, get_workspace_context

    app.dependency_overrides[get_auth_context] = lambda: AuthContext(
        user_id="user-1", email="user@example.com", token="token"
    )
    app.dependency_overrides[get_workspace_context] = lambda: WorkspaceContext(
        workspace_id="workspace-1",
        role="owner",
        plan="pro",
        auth=AuthContext(user_id="user-1", email="user@example.com", token="token"),
        db=None,
    )
    try:
        response = client.post(
            "/api/v1/projects",
            headers={"Authorization": "Bearer token", "X-Workspace-Id": "workspace-1"},
            json={},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"
