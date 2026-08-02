"""Role-matrix and tenant-isolation coverage for Team collaboration workflows."""
from __future__ import annotations

from unittest.mock import Mock, call, patch
from uuid import UUID

import pytest
from fastapi import HTTPException

from app.core.auth import AuthContext
from app.core.deps import WorkspaceContext, require_writer
from app.routers.collaboration import delete_comment, list_comments
from app.routers.tasks import approve_task, list_tasks, reject_task, submit_task_for_approval

WORKSPACE_A = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
WORKSPACE_B = "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"
USER_ID = "11111111-1111-1111-1111-111111111111"
OTHER_USER_ID = "22222222-2222-2222-2222-222222222222"
TASK_ID = "33333333-3333-3333-3333-333333333333"
COMMENT_ID = UUID("44444444-4444-4444-4444-444444444444")


def _context(*, role: str, db: Mock | None = None, workspace_id: str = WORKSPACE_A):
    return WorkspaceContext(
        workspace_id=workspace_id,
        role=role,
        plan="team",
        auth=AuthContext(user_id=USER_ID, email="user@example.com", token="token"),
        db=db or Mock(),
    )


def _query(data) -> Mock:
    query = Mock()
    for method in (
        "select",
        "eq",
        "maybe_single",
        "order",
        "lte",
        "delete",
        "limit",
    ):
        getattr(query, method).return_value = query
    query.execute.return_value = Mock(data=data)
    return query


@pytest.mark.parametrize("role", ["owner", "admin", "member"])
def test_owner_admin_and_member_are_writers(role):
    ctx = _context(role=role)

    assert require_writer(ctx) is ctx


def test_viewer_is_read_only_across_team_mutations():
    ctx = _context(role="viewer")

    with pytest.raises(HTTPException) as exc_info:
        require_writer(ctx)

    assert exc_info.value.status_code == 403
    assert exc_info.value.detail["error"]["code"] == "read_only"


@pytest.mark.parametrize(
    ("role", "review", "decision"),
    [
        ("owner", approve_task, "approved"),
        ("owner", reject_task, "rejected"),
        ("admin", approve_task, "approved"),
        ("admin", reject_task, "rejected"),
    ],
)
def test_owner_and_admin_can_approve_or_reject_pending_tasks(role, review, decision):
    updated = {
        "id": TASK_ID,
        "workspace_id": WORKSPACE_A,
        "title": "Approve artwork",
        "approval_status": decision,
        "approval_reviewed_by": USER_ID,
        "status": "done" if decision == "approved" else "todo",
        "completed_at": "2026-08-02T18:00:00Z" if decision == "approved" else None,
    }
    db = Mock()
    rpc = Mock()
    rpc.execute.return_value = Mock(data=updated)
    db.rpc.return_value = rpc
    service = Mock()
    service.table.return_value = _query([])

    with patch("app.routers.tasks.get_service_client", return_value=service):
        result = review(TASK_ID, "Reviewed", _context(role=role, db=db))

    assert result == updated
    db.rpc.assert_called_once_with(
        "review_task_approval",
        {"p_task_id": TASK_ID, "p_decision": decision, "p_note": "Reviewed"},
    )


@pytest.mark.parametrize("role", ["member", "viewer"])
@pytest.mark.parametrize("review", [approve_task, reject_task])
def test_member_and_viewer_cannot_review_task_approvals(role, review):
    db = Mock()

    with pytest.raises(HTTPException) as exc_info:
        review(TASK_ID, None, _context(role=role, db=db))

    assert exc_info.value.status_code == 403
    assert exc_info.value.detail["error"]["code"] == "reviewer_required"
    db.rpc.assert_not_called()


@pytest.mark.parametrize("role", ["owner", "admin", "member"])
def test_all_team_writers_can_submit_a_task_for_approval(role):
    current = {
        "id": TASK_ID,
        "workspace_id": WORKSPACE_A,
        "title": "Approve artwork",
        "approval_status": "not_required",
    }
    updated = {**current, "approval_status": "pending", "approval_submitted_by": USER_ID}
    db = Mock()
    db.table.return_value = _query(current)
    rpc = Mock()
    rpc.execute.return_value = Mock(data=updated)
    db.rpc.return_value = rpc
    service = Mock()
    service.table.return_value = _query([])

    with patch("app.routers.tasks.get_service_client", return_value=service):
        result = submit_task_for_approval(TASK_ID, _context(role=role, db=db))

    assert result == updated
    db.rpc.assert_called_once_with("submit_task_for_approval", {"p_task_id": TASK_ID})


def test_task_from_another_workspace_is_hidden_before_approval_submission():
    db = Mock()
    task_query = _query(None)
    db.table.return_value = task_query

    with pytest.raises(HTTPException) as exc_info:
        submit_task_for_approval(TASK_ID, _context(role="member", db=db))

    assert exc_info.value.status_code == 404
    assert exc_info.value.detail["error"]["code"] == "not_found"
    task_query.eq.assert_any_call("workspace_id", WORKSPACE_A)
    db.rpc.assert_not_called()


def test_task_listing_is_scoped_to_the_active_workspace():
    db = Mock()
    query = _query([{"id": TASK_ID, "workspace_id": WORKSPACE_A}])
    db.table.return_value = query

    result = list_tasks(ctx=_context(role="viewer", db=db))

    assert result == [{"id": TASK_ID, "workspace_id": WORKSPACE_A}]
    query.eq.assert_any_call("workspace_id", WORKSPACE_A)


@pytest.mark.parametrize("role", ["owner", "admin"])
def test_owner_and_admin_can_moderate_another_authors_comment(role):
    db = Mock()
    query = _query(
        {
            "id": str(COMMENT_ID),
            "author_id": OTHER_USER_ID,
            "target_type": "task",
            "target_id": TASK_ID,
        }
    )
    db.table.return_value = query

    with patch("app.routers.collaboration.get_service_client"):
        delete_comment(COMMENT_ID, _context(role=role, db=db))

    query.eq.assert_any_call("workspace_id", WORKSPACE_A)
    query.delete.assert_called_once()


@pytest.mark.parametrize("role", ["member", "viewer"])
def test_member_and_viewer_cannot_moderate_another_authors_comment(role):
    db = Mock()
    query = _query(
        {
            "id": str(COMMENT_ID),
            "author_id": OTHER_USER_ID,
            "target_type": "task",
            "target_id": TASK_ID,
        }
    )
    db.table.return_value = query

    with pytest.raises(HTTPException) as exc_info:
        delete_comment(COMMENT_ID, _context(role=role, db=db))

    assert exc_info.value.status_code == 403
    assert exc_info.value.detail["error"]["code"] == "forbidden"
    query.delete.assert_not_called()


def test_comments_for_a_target_in_another_workspace_are_hidden():
    db = Mock()
    target_query = _query(None)
    db.table.return_value = target_query

    with pytest.raises(HTTPException) as exc_info:
        list_comments("task", UUID(TASK_ID), _context(role="viewer", db=db))

    assert exc_info.value.status_code == 404
    assert exc_info.value.detail["error"]["code"] == "not_found"
    target_query.eq.assert_any_call("workspace_id", WORKSPACE_A)
    assert db.table.call_args_list == [call("tasks")]
