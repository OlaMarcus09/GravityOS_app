"""Unit coverage for role and plan authorization boundaries."""
from __future__ import annotations

from unittest.mock import Mock, patch

import pytest
from fastapi import HTTPException

from app.core.auth import AuthContext
from app.core.deps import WorkspaceContext, get_workspace_context, require_pro, require_writer
from app.routers.projects import create_project
from app.routers.workspaces import create_invitation
from app.schemas.projects import ProjectCreate
from app.schemas.workspaces import MemberInvite


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


def test_missing_workspace_membership_is_forbidden_when_supabase_returns_none():
    db = Mock()
    query = Mock()
    query.select.return_value = query
    query.eq.return_value = query
    query.maybe_single.return_value = query
    query.execute.return_value = None
    db.table.return_value = query

    with pytest.raises(HTTPException) as exc_info:
        get_workspace_context(
            x_workspace_id="00000000-0000-0000-0000-000000000000",
            auth=AuthContext(user_id="user-1", email="user@example.com", token="token"),
            db=db,
        )

    assert exc_info.value.status_code == 403
    assert exc_info.value.detail["error"]["code"] == "not_a_member"


def test_create_invitation_handles_missing_existing_invite_response():
    query = Mock()
    query.select.return_value = query
    query.eq.return_value = query
    query.maybe_single.return_value = query
    query.insert.return_value = query
    query.execute.side_effect = [
        None,
        Mock(data=[{
            "id": "invite-1",
            "workspace_id": "workspace-1",
            "email": "new@example.com",
            "role": "member",
        }]),
    ]
    service = Mock()
    service.table.return_value = query

    with (
        patch("app.routers.workspaces.get_service_client", return_value=service),
        patch("app.routers.workspaces._send_invitation_email", return_value=True),
    ):
        result = create_invitation(
            MemberInvite(email="new@example.com", role="member"),
            workspace_context(plan="team"),
        )

    assert result["id"] == "invite-1"
    assert result["email_sent"] is True
    query.insert.assert_called_once()
