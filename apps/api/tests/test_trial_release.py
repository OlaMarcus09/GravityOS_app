"""Trial release boundaries: trusted entitlements and no payment collection."""
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.core.auth import AuthContext
from app.core.config import Settings
from app.core.deps import WorkspaceContext, get_workspace_context
from app.main import app
from app.routers.billing import billing_details
from app.schemas.workspaces import WorkspaceCreate, WorkspaceUpdate


def context_for(row):
    query = Mock()
    for name in ("select", "eq", "maybe_single"):
        getattr(query, name).return_value = query
    query.execute.return_value = SimpleNamespace(data=row)
    db = Mock()
    db.table.return_value = query
    return WorkspaceContext(
        workspace_id="workspace-1", role="owner", plan="free", db=db,
        auth=AuthContext(user_id="user-1", email="test@example.com", token="test"),
    )


@pytest.mark.parametrize("method,path", [
    ("POST", "/checkout"), ("GET", "/portal"), ("POST", "/verify"), ("POST", "/webhook"),
])
def test_payment_routes_fail_closed_without_database_or_network(method, path):
    with (
        patch("app.core.db.get_service_client", side_effect=AssertionError("No payment writes")),
        patch("httpx.HTTPTransport.handle_request", side_effect=AssertionError("No provider requests")),
    ):
        response = TestClient(app).request(method, "/api/v1/billing" + path)
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "billing_checkout_disabled"


def test_checkout_flag_defaults_false_and_does_not_enable_collection(monkeypatch):
    monkeypatch.delenv("BILLING_CHECKOUT_ENABLED", raising=False)
    assert Settings(_env_file=None).billing_checkout_enabled is False
    monkeypatch.setenv("BILLING_CHECKOUT_ENABLED", "true")
    assert TestClient(app).post("/api/v1/billing/checkout").status_code == 503


@pytest.mark.parametrize("active", [True, False])
def test_trial_details_show_effective_plan_and_never_offer_checkout(active):
    at = datetime.now(timezone.utc)
    start = at - timedelta(hours=1 if active else 169)
    row = {"plan":"free", "billing_status":"none", "current_period_start":None,
           "current_period_end":None, "trial_started_at":start.isoformat(),
           "trial_expires_at":(start + timedelta(hours=168)).isoformat()}
    result = billing_details(context_for(row))
    assert result["plan"] == ("pro" if active else "free")
    assert result["trial_status"] == ("active" if active else "expired")
    assert result["checkout_eligible"] is False
    assert result["trial_expires_at"] == row["trial_expires_at"]
    assert row["plan"] == "free"


def test_workspace_context_uses_the_trial_for_feature_authorization():
    at = datetime.now(timezone.utc)
    row = {"plan":"free", "billing_status":"none", "trial_started_at":at.isoformat(),
           "trial_expires_at":(at + timedelta(hours=168)).isoformat()}
    ctx = context_for({"role":"owner", "workspaces":row})
    loaded = get_workspace_context(x_workspace_id=ctx.workspace_id, auth=ctx.auth, db=ctx.db)
    assert loaded.plan == "pro"
    row["trial_started_at"] = (at - timedelta(hours=169)).isoformat()
    row["trial_expires_at"] = (at - timedelta(hours=1)).isoformat()
    assert get_workspace_context(x_workspace_id=ctx.workspace_id, auth=ctx.auth, db=ctx.db).plan == "free"


@pytest.mark.parametrize("schema", [WorkspaceCreate, WorkspaceUpdate])
@pytest.mark.parametrize("entitlement", ["plan", "trial_started_at", "trial_expires_at", "billing_status"])
def test_clients_cannot_submit_entitlement_fields(schema, entitlement):
    with pytest.raises(ValidationError):
        schema.model_validate({"name":"Workspace", entitlement:"untrusted"})
