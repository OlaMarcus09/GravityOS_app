"""Existing-user claim API boundaries and trial fallback."""
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from fastapi import HTTPException

from app.core.auth import AuthContext
from app.core.deps import WorkspaceContext, get_workspace_context
from app.routers import existing_trial
from app.services.entitlements import effective_plan


def context(role="owner", workspace_id="selected"):
    return WorkspaceContext(
        workspace_id=workspace_id, role=role, plan="free", db=Mock(),
        auth=AuthContext(user_id="owner", email="owner@example.com", token="jwt"),
    )


def rpc_result(monkeypatch, payload):
    client = Mock()
    client.rpc.return_value.execute.return_value = SimpleNamespace(data=payload)
    monkeypatch.setattr(existing_trial, "get_service_client", lambda: client)
    return client


@pytest.mark.parametrize("role", ["member", "admin", "viewer"])
def test_only_owner_can_ask_or_claim(monkeypatch, role):
    client = rpc_result(monkeypatch, {"eligible": True, "reason": "eligible"})
    with pytest.raises(HTTPException) as eligibility:
        existing_trial.existing_trial_eligibility(context(role))
    with pytest.raises(HTTPException) as claim:
        existing_trial.claim_existing_trial(context(role))
    assert eligibility.value.status_code == claim.value.status_code == 403
    client.rpc.assert_not_called()


def test_rpc_identity_and_workspace_come_from_verified_context(monkeypatch):
    client = rpc_result(monkeypatch, {"eligible": True, "reason": "eligible"})
    assert existing_trial.existing_trial_eligibility(context())["eligible"] is True
    client.rpc.assert_called_once_with("existing_user_trial_eligibility", {
        "p_owner_id": "owner", "p_workspace_id": "selected",
    })


def test_foreign_workspace_fails_membership_guard_before_service_call(monkeypatch):
    client = rpc_result(monkeypatch, {"eligible": True, "reason": "eligible"})
    db = Mock()
    query = db.table.return_value
    query.select.return_value = query
    query.eq.return_value = query
    query.maybe_single.return_value = query
    query.execute.return_value = SimpleNamespace(data=None)
    with pytest.raises(HTTPException) as exc:
        get_workspace_context(x_workspace_id="foreign", auth=context().auth, db=db)
    assert exc.value.status_code == 403
    client.rpc.assert_not_called()


@pytest.mark.parametrize("reason", [
    "already_claimed", "email_confirmation_required", "paid_workspace_conflict",
    "not_owner", "not_eligible", "window_closed",
])
def test_ineligible_owner_cannot_activate(monkeypatch, reason):
    rpc_result(monkeypatch, {"reason": reason})
    with pytest.raises(HTTPException) as exc:
        existing_trial.claim_existing_trial(context())
    assert exc.value.detail["error"]["code"] == reason
    assert exc.value.status_code in (403, 409, 422)


def test_success_returns_exact_database_times(monkeypatch):
    started = datetime(2026, 11, 3, tzinfo=timezone.utc)
    expires = started + timedelta(seconds=604800)
    payload = {"reason": "activated", "trial_started_at": started.isoformat(),
               "trial_expires_at": expires.isoformat()}
    rpc_result(monkeypatch, payload)
    assert existing_trial.claim_existing_trial(context()) == payload
    row = {"plan": "free", "billing_status": "none", "trial_started_at": started.isoformat(),
           "trial_expires_at": expires.isoformat()}
    assert effective_plan(row, at=expires - timedelta(microseconds=1)) == "pro"
    assert effective_plan(row, at=expires) == "free"
