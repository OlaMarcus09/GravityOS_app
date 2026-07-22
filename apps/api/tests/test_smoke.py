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
