from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import Mock, patch

import pytest
from fastapi import HTTPException

from app.core.auth import AuthContext, verify_token
from app.core.deps import WorkspaceContext, require_writer
from app.core.rate_limit import _events, check_rate_limit
from app.routers.intelligence import compute_gravity_score, router


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


def test_gravity_score_compute_requires_writer():
    route = next(route for route in router.routes if route.path == "/gravity-score/compute")
    assert require_writer in {dependency.call for dependency in route.dependant.dependencies}
