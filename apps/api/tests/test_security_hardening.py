from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import Mock, patch

import pytest
from fastapi import HTTPException

from app.core.auth import AuthContext, verify_token
from app.core.deps import WorkspaceContext, require_writer
from app.core.rate_limit import _events, check_rate_limit
from app.routers.intelligence import compute_gravity_score, router
from app.routers.workspaces import admin_plan_audit, admin_set_plan, admin_set_user_status


def workspace_context(*, role: str = "member", db: Mock | None = None) -> WorkspaceContext:
    return WorkspaceContext(
        "workspace-security-test",
        role,
        "team",
        AuthContext("security-user", "user@example.com", "token"),
        db or Mock(),
    )


def test_jwt_rejects_unapproved_algorithm():
    with (
        patch("app.core.auth.jwt.get_unverified_header", return_value={"alg": "RS256"}),
        patch("app.core.auth.jwt.decode") as decode,
    ):
        with pytest.raises(HTTPException) as exc_info:
            verify_token("untrusted-token")
    assert exc_info.value.status_code == 401
    decode.assert_not_called()


def test_rate_limit_blocks_after_limit():
    key = "test:rate-limit"
    _events.pop(key, None)
    check_rate_limit(key, limit=2)
    check_rate_limit(key, limit=2)
    with pytest.raises(HTTPException) as exc_info:
        check_rate_limit(key, limit=2)
    assert exc_info.value.status_code == 429
    _events.pop(key, None)


def test_recent_gravity_score_enforces_cooldown():
    db, query = Mock(), Mock()
    query.select.return_value = query
    query.eq.return_value = query
    query.order.return_value = query
    query.limit.return_value = query
    query.execute.return_value = Mock(
        data=[{"computed_at": (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat()}]
    )
    db.table.return_value = query
    with pytest.raises(HTTPException) as exc_info:
        compute_gravity_score(workspace_context(db=db))
    assert exc_info.value.status_code == 429


def test_gravity_score_uses_service_role_only_for_snapshot_write():
    latest_query = Mock()
    for method in ("select", "eq", "order", "limit"):
        getattr(latest_query, method).return_value = latest_query
    latest_query.execute.return_value = Mock(data=[])
    user_db = Mock()
    user_db.table.return_value = latest_query

    inserted = {
        "id": "score-1",
        "workspace_id": "workspace-security-test",
        "overall": 42,
    }
    service_query = Mock()
    service_query.insert.return_value = service_query
    service_query.execute.return_value = Mock(data=[inserted])
    service_db = Mock()
    service_db.table.return_value = service_query
    scores = {
        "overall": 42,
        "consistency": 40,
        "organization": 41,
        "execution": 42,
        "marketing": 43,
        "collaboration": 44,
        "business_readiness": 45,
    }

    with (
        patch("app.routers.intelligence._compute_score", return_value=scores),
        patch("app.routers.intelligence.get_service_client", return_value=service_db),
    ):
        result = compute_gravity_score(workspace_context(db=user_db))

    assert result == inserted
    user_db.table.assert_called_once_with("gravity_scores")
    service_db.table.assert_called_once_with("gravity_scores")
    row = service_query.insert.call_args.args[0]
    assert row["workspace_id"] == "workspace-security-test"
    assert row["overall"] == 42
    assert set(row) == {"workspace_id", "computed_at", *scores}


def test_gravity_score_compute_requires_writer():
    route = next(route for route in router.routes if route.path == "/gravity-score/compute")
    assert require_writer in {dependency.call for dependency in route.dependant.dependencies}


def test_admin_plan_change_uses_atomic_audit_rpc():
    lookup = Mock()
    lookup.select.return_value = lookup
    lookup.eq.return_value = lookup
    lookup.maybe_single.return_value = lookup
    lookup.execute.return_value = Mock(data={"id": "workspace-1"})
    rpc = Mock()
    rpc.execute.return_value = Mock(data={"id": "workspace-1", "plan": "pro"})
    service = Mock()
    service.table.return_value = lookup
    service.rpc.return_value = rpc
    auth = AuthContext("admin-1", "admin@example.com", "token")

    with patch("app.routers.workspaces.get_service_client", return_value=service):
        result = admin_set_plan("workspace-1", "pro", auth)

    assert result["plan"] == "pro"
    service.rpc.assert_called_once_with(
        "admin_set_workspace_plan",
        {
            "p_workspace_id": "workspace-1",
            "p_new_plan": "pro",
            "p_actor_id": "admin-1",
            "p_actor_email": "admin@example.com",
        },
    )


def test_admin_plan_change_preserves_not_found_contract():
    lookup = Mock()
    lookup.select.return_value = lookup
    lookup.eq.return_value = lookup
    lookup.maybe_single.return_value = lookup
    lookup.execute.return_value = Mock(data=None)
    service = Mock()
    service.table.return_value = lookup
    auth = AuthContext("admin-1", "admin@example.com", "token")

    with (
        patch("app.routers.workspaces.get_service_client", return_value=service),
        pytest.raises(HTTPException) as exc_info,
    ):
        admin_set_plan("missing", "pro", auth)

    assert exc_info.value.status_code == 404
    service.rpc.assert_not_called()


def test_admin_plan_audit_is_newest_first_and_bounded():
    query = Mock()
    query.select.return_value = query
    query.order.return_value = query
    query.limit.return_value = query
    query.execute.return_value = Mock(data=[{"id": "audit-1"}])
    service = Mock()
    service.table.return_value = query
    auth = AuthContext("admin-1", "admin@example.com", "token")

    with patch("app.routers.workspaces.get_service_client", return_value=service):
        result = admin_plan_audit(auth, 25)

    assert result == [{"id": "audit-1"}]
    query.order.assert_called_once_with("created_at", desc=True)
    query.limit.assert_called_once_with(25)


def test_admin_cannot_suspend_own_account():
    auth = AuthContext("admin-1", "admin@example.com", "token")
    with pytest.raises(HTTPException) as exc_info:
        admin_set_user_status("admin-1", "suspend", auth)
    assert exc_info.value.status_code == 409


@pytest.mark.parametrize(
    ("action", "ban_duration"),
    [("suspend", "876000h"), ("reactivate", "none")],
)
def test_admin_account_status_change_is_audited(action, ban_duration):
    user = Mock(
        id="user-2",
        email="user@example.com",
        created_at="2026-01-01T00:00:00Z",
        last_sign_in_at=None,
        banned_until=None if action == "reactivate" else "2126-01-01T00:00:00Z",
    )
    auth_admin = Mock()
    auth_admin.get_user_by_id.return_value = Mock(user=user)
    auth_admin.update_user_by_id.return_value = Mock(user=user)
    audit = Mock()
    audit.insert.return_value = audit
    audit.execute.return_value = Mock(data=[{"id": "audit-1"}])
    service = Mock()
    service.auth.admin = auth_admin
    service.table.return_value = audit
    auth = AuthContext("admin-1", "admin@example.com", "token")

    with patch("app.routers.workspaces.get_service_client", return_value=service):
        result = admin_set_user_status("user-2", action, auth)

    assert result["id"] == "user-2"
    auth_admin.update_user_by_id.assert_called_once_with(
        "user-2", {"ban_duration": ban_duration}
    )
    audit.insert.assert_called_once_with(
        {
            "user_id": "user-2",
            "user_email": "user@example.com",
            "actor_id": "admin-1",
            "actor_email": "admin@example.com",
            "action": action,
        }
    )
