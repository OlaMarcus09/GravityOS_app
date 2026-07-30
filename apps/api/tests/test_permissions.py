"""Unit coverage for role and plan authorization boundaries."""
from __future__ import annotations

from unittest.mock import Mock

import pytest
from fastapi import HTTPException

from app.core.auth import AuthContext
from app.core.deps import WorkspaceContext, require_pro, require_writer
from app.routers.projects import create_project
from app.schemas.projects import ProjectCreate


def workspace_context(*, role: str = "owner", plan: str = "free", db: Mock | None = None):
    return WorkspaceContext(
        workspace_id="workspace-1",
        role=role,
        plan=plan,
        auth=AuthContext(user_id="user-1", email="user@example.com", token="token"),
        db=db or Mock(),
    )


def test_viewer_cannot_write():
    with pytest.raises(HTTPException) as exc_info:
        require_writer(workspace_context(role="viewer"))

    assert exc_info.value.status_code == 403
    assert exc_info.value.detail["error"]["code"] == "read_only"


def test_free_plan_cannot_use_pro_mutations():
    with pytest.raises(HTTPException) as exc_info:
        require_pro(workspace_context(plan="free"))

    assert exc_info.value.status_code == 403
    assert exc_info.value.detail["error"]["code"] == "plan_required"


def test_pro_plan_can_use_pro_mutations():
    ctx = workspace_context(plan="pro")
    assert require_pro(ctx) is ctx


def test_free_plan_project_limit_blocks_second_active_project():
    db = Mock()
    count_result = Mock(count=1)
    query = Mock()
    query.select.return_value = query
    query.eq.return_value = query
    query.in_.return_value = query
    query.execute.return_value = count_result
    db.table.return_value = query

    with pytest.raises(HTTPException) as exc_info:
        create_project(ProjectCreate(title="Second project"), workspace_context(db=db))

    assert exc_info.value.status_code == 403
    assert exc_info.value.detail["error"]["code"] == "plan_limit"
    query.insert.assert_not_called()
