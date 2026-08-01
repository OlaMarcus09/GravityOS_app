"""Unit coverage for role and plan authorization boundaries."""
from __future__ import annotations

from unittest.mock import Mock, patch

import pytest
from fastapi import HTTPException

from app.core.auth import AuthContext
from app.core.deps import WorkspaceContext, get_workspace_context, require_pro, require_writer
from app.routers.projects import create_project
from app.routers.workspaces import (
    accept_invitation,
    create_invitation,
    remove_member,
    resend_invitation,
    revoke_invitation,
    update_member,
)
from app.schemas.projects import ProjectCreate
from app.schemas.workspaces import MemberInvite, MemberUpdate


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
    assert query.insert.call_args_list[0].args[0]["email"] == "new@example.com"


def test_accept_invitation_returns_created_membership_and_workspace():
    db = Mock()
    rpc = Mock()
    rpc.execute.return_value = Mock(data=[{
        "membership_id": "membership-1",
        "workspace_id": "workspace-1",
    }])
    db.rpc.return_value = rpc

    result = accept_invitation(
        "invite-1",
        AuthContext(user_id="user-2", email="new@example.com", token="token"),
        db,
    )

    assert result == {"membership_id": "membership-1", "workspace_id": "workspace-1"}
    db.rpc.assert_called_once_with("accept_workspace_invitation", {"invitation_id": "invite-1"})


@pytest.mark.parametrize(
    ("database_message", "status_code", "error_code"),
    [
        ("invitation has expired", 410, "invite_expired"),
        ("invitation is no longer available", 409, "invite_unavailable"),
        ("invitation not found", 404, "not_found"),
    ],
)
def test_accept_invitation_maps_database_errors(database_message, status_code, error_code):
    db = Mock()
    db.rpc.side_effect = RuntimeError(database_message)

    with pytest.raises(HTTPException) as exc_info:
        accept_invitation(
            "invite-1",
            AuthContext(user_id="user-2", email="new@example.com", token="token"),
            db,
        )

    assert exc_info.value.status_code == status_code
    assert exc_info.value.detail["error"]["code"] == error_code


def test_resend_invitation_refreshes_expiry_and_sends_email():
    query = Mock()
    query.update.return_value = query
    query.eq.return_value = query
    query.is_.return_value = query
    query.execute.return_value = Mock(data=[{
        "id": "invite-1",
        "workspace_id": "workspace-1",
        "email": "new@example.com",
        "role": "viewer",
    }])
    service = Mock()
    service.table.return_value = query

    with (
        patch("app.routers.workspaces.get_service_client", return_value=service),
        patch("app.routers.workspaces._send_invitation_email", return_value=True) as send_email,
    ):
        result = resend_invitation("invite-1", workspace_context(plan="team"))

    assert result["email_sent"] is True
    send_email.assert_called_once_with("new@example.com")
    update = query.update.call_args.args[0]
    assert update["revoked_at"] is None
    assert update["expires_at"] > update["invited_at"]


def test_revoke_invitation_marks_only_a_pending_workspace_invite():
    query = Mock()
    query.update.return_value = query
    query.eq.return_value = query
    query.is_.return_value = query
    query.execute.return_value = Mock(data=[])
    service = Mock()
    service.table.return_value = query

    with patch("app.routers.workspaces.get_service_client", return_value=service):
        revoke_invitation("invite-1", workspace_context(plan="team"))

    assert query.update.call_args.args[0]["revoked_at"] is not None
    query.eq.assert_any_call("id", "invite-1")
    query.eq.assert_any_call("workspace_id", "workspace-1")
    query.is_.assert_called_once_with("accepted_at", "null")


def member_service(member: dict | None, mutation_data: list[dict] | None = None):
    select_query = Mock()
    select_query.select.return_value = select_query
    select_query.eq.return_value = select_query
    select_query.maybe_single.return_value = select_query
    select_query.execute.return_value = Mock(data=member) if member is not None else None

    mutation_query = Mock()
    mutation_query.update.return_value = mutation_query
    mutation_query.delete.return_value = mutation_query
    mutation_query.eq.return_value = mutation_query
    mutation_query.execute.return_value = Mock(data=mutation_data or [])

    service = Mock()
    service.table.side_effect = [select_query, mutation_query]
    return service, mutation_query


@pytest.mark.parametrize("action", ["update", "remove"])
def test_owner_membership_cannot_be_changed_or_removed(action):
    service, mutation = member_service({"id": "membership-1", "user_id": "user-1", "role": "owner"})

    with patch("app.routers.workspaces.get_service_client", return_value=service):
        with pytest.raises(HTTPException) as exc_info:
            if action == "update":
                update_member("user-1", MemberUpdate(role="member"), workspace_context(role="owner"))
            else:
                remove_member("user-1", workspace_context(role="owner"))

    assert exc_info.value.status_code == 409
    assert exc_info.value.detail["error"]["code"] == "owner_protected"
    mutation.update.assert_not_called()
    mutation.delete.assert_not_called()


@pytest.mark.parametrize("action", ["update", "remove"])
def test_admin_cannot_manage_another_admin(action):
    service, mutation = member_service({"id": "membership-2", "user_id": "user-2", "role": "admin"})

    with patch("app.routers.workspaces.get_service_client", return_value=service):
        with pytest.raises(HTTPException) as exc_info:
            if action == "update":
                update_member("user-2", MemberUpdate(role="member"), workspace_context(role="admin"))
            else:
                remove_member("user-2", workspace_context(role="admin"))

    assert exc_info.value.status_code == 403
    assert exc_info.value.detail["error"]["code"] == "owner_required"
    mutation.update.assert_not_called()
    mutation.delete.assert_not_called()


@pytest.mark.parametrize("action", ["update", "remove"])
def test_admin_cannot_change_or_remove_self(action):
    service, mutation = member_service({"id": "membership-1", "user_id": "user-1", "role": "admin"})

    with patch("app.routers.workspaces.get_service_client", return_value=service):
        with pytest.raises(HTTPException) as exc_info:
            if action == "update":
                update_member("user-1", MemberUpdate(role="member"), workspace_context(role="admin"))
            else:
                remove_member("user-1", workspace_context(role="admin"))

    assert exc_info.value.status_code == 409
    assert exc_info.value.detail["error"]["code"] == "self_management_forbidden"
    mutation.update.assert_not_called()
    mutation.delete.assert_not_called()


@pytest.mark.parametrize("action", ["update", "remove"])
def test_member_management_returns_not_found_before_mutating(action):
    service, mutation = member_service(None)

    with patch("app.routers.workspaces.get_service_client", return_value=service):
        with pytest.raises(HTTPException) as exc_info:
            if action == "update":
                update_member("missing-user", MemberUpdate(role="member"), workspace_context(role="owner"))
            else:
                remove_member("missing-user", workspace_context(role="owner"))

    assert exc_info.value.status_code == 404
    assert exc_info.value.detail["error"]["code"] == "not_found"
    mutation.update.assert_not_called()
    mutation.delete.assert_not_called()


def test_owner_can_promote_member_to_admin():
    updated = {"id": "membership-2", "user_id": "user-2", "role": "admin"}
    service, mutation = member_service(
        {"id": "membership-2", "user_id": "user-2", "role": "member"},
        [updated],
    )

    with (
        patch("app.routers.workspaces.get_service_client", return_value=service),
        patch("app.routers.workspaces._notify") as notify,
    ):
        result = update_member("user-2", MemberUpdate(role="admin"), workspace_context(role="owner"))

    assert result == updated
    mutation.update.assert_called_once_with({"role": "admin"})
    notify.assert_called_once()


def test_admin_cannot_invite_another_admin():
    with patch("app.routers.workspaces.get_service_client"):
        with pytest.raises(HTTPException) as exc_info:
            create_invitation(MemberInvite(email="new@example.com", role="admin"), workspace_context(role="admin", plan="team"))
    assert exc_info.value.status_code == 403
    assert exc_info.value.detail["error"]["code"] == "owner_required"


def test_admin_can_remove_regular_member():
    deleted = {"id": "membership-2", "user_id": "user-2", "role": "member"}
    service, mutation = member_service(deleted, [deleted])

    with patch("app.routers.workspaces.get_service_client", return_value=service):
        remove_member("user-2", workspace_context(role="admin"))

    mutation.delete.assert_called_once_with()
