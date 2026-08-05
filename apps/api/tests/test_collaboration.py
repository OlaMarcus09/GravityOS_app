"""Collaboration route behavior that does not require a live Supabase project."""
from __future__ import annotations

from unittest.mock import Mock, patch
from uuid import UUID

import pytest
from fastapi import HTTPException

from app.core.auth import AuthContext
from app.core.deps import WorkspaceContext
from app.routers.collaboration import _notify_mentions, delete_comment, list_activity


def workspace_context(*, role: str = "member", user_id: str = "11111111-1111-1111-1111-111111111111"):
    return WorkspaceContext(
        workspace_id="aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
        role=role,
        plan="team",
        auth=AuthContext(user_id=user_id, email="member@example.com", token="token"),
        db=Mock(),
    )


def test_mentions_notify_only_workspace_members_and_exclude_author():
    ctx = workspace_context()
    member_id = "22222222-2222-2222-2222-222222222222"
    outsider_id = "33333333-3333-3333-3333-333333333333"
    query = Mock()
    query.select.return_value = query
    query.eq.return_value = query
    query.in_.return_value = query
    query.execute.return_value = Mock(data=[{"user_id": member_id}])
    service = Mock()
    service.table.return_value = query

    body = (
        f"Hi @[Me]({ctx.auth.user_id}), @[Member]({member_id}), "
        f"and @[Outsider]({outsider_id})"
    )
    comment = {
        "id": "comment-1",
        "target_type": "task",
        "target_id": "task-1",
    }
    with (
        patch("app.routers.collaboration.get_service_client", return_value=service),
        patch("app.routers.collaboration.create_notification") as notify,
    ):
        _notify_mentions(ctx, body, comment, {"title": "Finish mix"})

    queried_ids = set(query.in_.call_args.args[1])
    assert queried_ids == {member_id, outsider_id}
    payload = notify.call_args.kwargs
    assert payload["recipient_id"] == member_id
    assert payload["kind"] == "comment_mention"
    assert payload["dedupe_key"] == f"comment-mention:comment-1:{member_id}"


def test_malformed_mention_is_ignored():
    ctx = workspace_context()

    with patch("app.routers.collaboration.get_service_client") as service:
        _notify_mentions(
            ctx,
            "@[Broken](------------------------------------)",
            {"id": "comment-1", "target_type": "task", "target_id": "task-1"},
            {"title": "Finish mix"},
        )

    service.assert_not_called()


def test_member_cannot_delete_another_authors_comment():
    ctx = workspace_context(role="member")
    query = Mock()
    query.select.return_value = query
    query.eq.return_value = query
    query.maybe_single.return_value = query
    query.execute.return_value = Mock(data={
        "id": "44444444-4444-4444-4444-444444444444",
        "author_id": "22222222-2222-2222-2222-222222222222",
        "target_type": "project",
        "target_id": "55555555-5555-5555-5555-555555555555",
    })
    ctx.db.table.return_value = query

    with pytest.raises(HTTPException) as exc_info:
        delete_comment(UUID("44444444-4444-4444-4444-444444444444"), ctx)

    assert exc_info.value.status_code == 403
    assert exc_info.value.detail["error"]["code"] == "forbidden"
    query.delete.assert_not_called()


def test_admin_can_delete_another_authors_comment():
    ctx = workspace_context(role="admin")
    query = Mock()
    query.select.return_value = query
    query.eq.return_value = query
    query.maybe_single.return_value = query
    query.delete.return_value = query
    query.execute.side_effect = [Mock(data={
        "id": "44444444-4444-4444-4444-444444444444",
        "author_id": "22222222-2222-2222-2222-222222222222",
        "target_type": "project",
        "target_id": "55555555-5555-5555-5555-555555555555",
    }), Mock(data=[])]
    ctx.db.table.return_value = query

    with patch("app.routers.collaboration.get_service_client"):
        delete_comment(UUID("44444444-4444-4444-4444-444444444444"), ctx)

    query.delete.assert_called_once()


def test_activity_filters_preserve_workspace_scope():
    ctx = workspace_context(role="viewer")
    project_id = UUID("55555555-5555-5555-5555-555555555555")
    member_id = UUID("22222222-2222-2222-2222-222222222222")
    task_query = Mock()
    task_query.select.return_value = task_query
    task_query.eq.return_value = task_query
    task_query.execute.return_value = Mock(data=[{"id": "66666666-6666-6666-6666-666666666666"}])
    activity_query = Mock()
    for method in ("select", "eq", "or_", "order", "limit"):
        getattr(activity_query, method).return_value = activity_query
    activity_query.execute.return_value = Mock(data=[])
    ctx.db.table.side_effect = [activity_query, task_query]

    with patch("app.routers.collaboration.get_service_client"):
        result = list_activity(
            limit=25,
            before=None,
            project_id=project_id,
            member_id=member_id,
            event_type="task_approved",
            ctx=ctx,
        )

    assert result == []
    activity_query.eq.assert_any_call("workspace_id", ctx.workspace_id)
    activity_query.eq.assert_any_call("actor_id", str(member_id))
    activity_query.eq.assert_any_call("event_type", "task_approved")
    task_query.eq.assert_any_call("workspace_id", ctx.workspace_id)
    task_query.eq.assert_any_call("project_id", str(project_id))
    project_filter = activity_query.or_.call_args.args[0]
    assert f"target_id.eq.{project_id}" in project_filter
    assert "target_id.in.(66666666-6666-6666-6666-666666666666)" in project_filter


def test_activity_filters_are_optional_and_before_still_paginates():
    ctx = workspace_context(role="viewer")
    activity_query = Mock()
    for method in ("select", "eq", "lt", "order", "limit"):
        getattr(activity_query, method).return_value = activity_query
    activity_query.execute.return_value = Mock(data=[])
    ctx.db.table.return_value = activity_query

    with patch("app.routers.collaboration.get_service_client"):
        result = list_activity(
            limit=50,
            before="2026-08-01T00:00:00Z",
            project_id=None,
            member_id=None,
            event_type=None,
            ctx=ctx,
        )

    assert result == []
    activity_query.eq.assert_called_once_with("workspace_id", ctx.workspace_id)
    activity_query.lt.assert_called_once_with("created_at", "2026-08-01T00:00:00Z")
    activity_query.or_.assert_not_called()
