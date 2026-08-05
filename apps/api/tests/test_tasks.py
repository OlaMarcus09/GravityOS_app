"""Task assignment collaboration behavior."""
from __future__ import annotations

from unittest.mock import Mock, patch

import pytest
from fastapi import HTTPException

from app.core.auth import AuthContext
from app.core.deps import WorkspaceContext
from app.routers.tasks import (
    _notify_approval,
    approve_task,
    delete_task,
    create_task,
    reject_task,
    submit_task_for_approval,
    update_task,
)
from app.schemas.tasks import TaskCreate, TaskUpdate

ASSIGNEE_ID = "00000000-0000-0000-0000-000000000002"


def _query(data) -> Mock:
    query = Mock()
    for method in ("select", "eq", "in_", "maybe_single", "insert", "update"):
        getattr(query, method).return_value = query
    query.execute.return_value = Mock(data=data)
    return query


def _context(db: Mock) -> WorkspaceContext:
    return WorkspaceContext(
        workspace_id="workspace-1",
        role="member",
        plan="team",
        auth=AuthContext(user_id="user-1", email="user@example.com", token="token"),
        db=db,
    )


def test_create_task_rejects_assignee_outside_workspace():
    member_query = _query(None)
    db = Mock()
    db.table.return_value = member_query

    with pytest.raises(HTTPException) as exc_info:
        create_task(TaskCreate(title="Draft launch", assignee_id=ASSIGNEE_ID), _context(db))

    assert exc_info.value.status_code == 422
    assert exc_info.value.detail["error"]["code"] == "invalid_assignee"
    member_query.insert.assert_not_called()


def test_create_task_notifies_workspace_assignee_and_records_activity():
    task = {
        "id": "task-1",
        "title": "Draft launch",
        "project_id": "project-1",
        "assignee_id": ASSIGNEE_ID,
        "status": "todo",
    }
    member_query = _query({"user_id": ASSIGNEE_ID})
    task_query = _query([task])
    db = Mock()
    db.table.side_effect = [member_query, task_query]
    service_query = _query([{}])
    service = Mock()
    service.table.return_value = service_query

    with (
        patch("app.routers.tasks.get_service_client", return_value=service),
        patch("app.routers.tasks.create_notification") as notify,
    ):
        result = create_task(
            TaskCreate(title="Draft launch", assignee_id=ASSIGNEE_ID),
            _context(db),
        )

    assert result == task
    assert service.table.call_args_list[0].args[0] == "workspace_activity_events"
    notification = notify.call_args.kwargs
    assert notification["recipient_id"] == ASSIGNEE_ID
    assert notification["kind"] == "task_assigned"
    assert notification["metadata"]["task_id"] == "task-1"
    assert notification["dedupe_key"].startswith("task-assigned:task-1:")


def test_update_task_notifies_only_when_assignee_changes():
    current = {"id": "task-1", "title": "Draft launch", "assignee_id": None}
    updated = {**current, "assignee_id": ASSIGNEE_ID, "status": "todo"}
    get_query = _query(current)
    member_query = _query({"user_id": ASSIGNEE_ID})
    update_query = _query([updated])
    db = Mock()
    db.table.side_effect = [get_query, member_query, update_query]
    service_query = _query([{}])
    service = Mock()
    service.table.return_value = service_query

    with (
        patch("app.routers.tasks.get_service_client", return_value=service),
        patch("app.routers.tasks.create_notification") as notify,
    ):
        result = update_task("task-1", TaskUpdate(assignee_id=ASSIGNEE_ID), _context(db))

    assert result == updated
    assert [call.args[0] for call in service.table.call_args_list] == ["workspace_activity_events"]
    notify.assert_called_once()


def test_update_task_does_not_notify_when_assignee_is_unchanged():
    current = {"id": "task-1", "title": "Draft launch", "assignee_id": ASSIGNEE_ID}
    updated = {**current, "status": "doing"}
    get_query = _query(current)
    update_query = _query([updated])
    db = Mock()
    db.table.side_effect = [get_query, update_query]
    service = Mock()
    service.table.return_value = _query([{}])

    with patch("app.routers.tasks.get_service_client", return_value=service):
        result = update_task("task-1", TaskUpdate(status="doing"), _context(db))

    assert result == updated
    assert [call.args[0] for call in service.table.call_args_list] == [
        "workspace_activity_events",
    ]


def test_approval_request_notifies_other_workspace_reviewers() -> None:
    reviewers = _query([
        {"user_id": "user-1"},
        {"user_id": "owner-1"},
        {"user_id": "admin-1"},
    ])
    service = Mock()
    service.table.return_value = reviewers
    task = {
        "id": "task-1",
        "title": "Draft launch",
        "updated_at": "2026-08-05T10:00:00Z",
    }

    with (
        patch("app.routers.tasks.get_service_client", return_value=service),
        patch("app.routers.tasks.create_notification") as notify,
    ):
        _notify_approval(_context(Mock()), task, "submitted")

    assert {call.kwargs["recipient_id"] for call in notify.call_args_list} == {
        "owner-1",
        "admin-1",
    }
    assert all(call.kwargs["kind"] == "task_approval_requested" for call in notify.call_args_list)
    assert all(call.kwargs["action_url"] == "/tasks" for call in notify.call_args_list)


def test_approval_decision_notifies_submitter_and_assignee_once_each() -> None:
    service = Mock()
    task = {
        "id": "task-1",
        "title": "Draft launch",
        "approval_submitted_by": "submitter-1",
        "assignee_id": "assignee-1",
        "approval_reviewed_at": "2026-08-05T11:00:00Z",
    }

    with (
        patch("app.routers.tasks.get_service_client", return_value=service),
        patch("app.routers.tasks.create_notification") as notify,
    ):
        _notify_approval(_context(Mock()), task, "approved")

    assert {call.kwargs["recipient_id"] for call in notify.call_args_list} == {
        "submitter-1",
        "assignee-1",
    }
    assert all(call.kwargs["kind"] == "task_approved" for call in notify.call_args_list)
    assert all("2026-08-05T11:00:00Z" in call.kwargs["dedupe_key"] for call in notify.call_args_list)


def test_task_mutation_succeeds_when_collaboration_writes_fail():
    task = {
        "id": "task-1",
        "title": "Draft launch",
        "assignee_id": ASSIGNEE_ID,
        "status": "todo",
    }
    member_query = _query({"user_id": ASSIGNEE_ID})
    task_query = _query([task])
    db = Mock()
    db.table.side_effect = [member_query, task_query]
    service_query = _query([])
    service_query.execute.side_effect = RuntimeError("supporting table unavailable")
    service = Mock()
    service.table.return_value = service_query

    with patch("app.routers.tasks.get_service_client", return_value=service):
        result = create_task(
            TaskCreate(title="Draft launch", assignee_id=ASSIGNEE_ID),
            _context(db),
        )

    assert result == task


def test_update_task_can_clear_assignee():
    current = {"id": "task-1", "title": "Draft launch", "assignee_id": ASSIGNEE_ID}
    updated = {**current, "assignee_id": None, "status": "todo"}
    get_query = _query(current)
    update_query = _query([updated])
    db = Mock()
    db.table.side_effect = [get_query, update_query]
    service = Mock()
    service.table.return_value = _query([{}])

    with patch("app.routers.tasks.get_service_client", return_value=service):
        result = update_task("task-1", TaskUpdate(assignee_id=None), _context(db))

    assert result["assignee_id"] is None
    assert update_query.update.call_args.args[0]["assignee_id"] is None
    assert [call.args[0] for call in service.table.call_args_list] == ["workspace_activity_events"]


def test_team_member_can_submit_task_for_approval():
    current = {"id": "task-1", "title": "Draft launch", "approval_status": "not_required"}
    updated = {**current, "approval_status": "pending", "approval_submitted_by": "user-1"}
    get_query = _query(current)
    db = Mock()
    db.table.side_effect = [get_query]
    rpc = Mock()
    rpc.execute.return_value = Mock(data=updated)
    db.rpc.return_value = rpc
    service = Mock()
    service.table.return_value = _query([{}])

    with patch("app.routers.tasks.get_service_client", return_value=service):
        result = submit_task_for_approval("task-1", _context(db))

    assert result == updated
    db.rpc.assert_called_once_with("submit_task_for_approval", {"p_task_id": "task-1"})


def test_only_admins_can_approve_pending_task():
    current = {"id": "task-1", "title": "Draft launch", "approval_status": "pending"}
    updated = {
        **current,
        "approval_status": "approved",
        "approval_reviewed_by": "user-1",
        "status": "done",
        "completed_at": "2026-08-02T18:00:00Z",
    }
    get_query = _query(current)
    db = Mock()
    db.table.side_effect = [get_query]
    rpc = Mock()
    rpc.execute.return_value = Mock(data=updated)
    db.rpc.return_value = rpc
    ctx = _context(db)
    ctx.role = "admin"
    service = Mock()
    service.table.return_value = _query([{}])

    with patch("app.routers.tasks.get_service_client", return_value=service):
        result = approve_task("task-1", None, ctx)

    assert result == updated
    db.rpc.assert_called_once_with("review_task_approval", {"p_task_id": "task-1", "p_decision": "approved", "p_note": None})
    activity_payloads = [
        call.args[0]
        for call in service.table.return_value.insert.call_args_list
        if isinstance(call.args[0], dict) and "event_type" in call.args[0]
    ]
    assert [payload["event_type"] for payload in activity_payloads] == [
        "task_approved",
        "task_completed",
    ]


def test_rejection_reopens_task_for_changes():
    updated = {
        "id": "task-1",
        "title": "Draft launch",
        "approval_status": "rejected",
        "approval_reviewed_by": "user-1",
        "approval_note": "Needs changes",
        "status": "todo",
        "completed_at": None,
    }
    db = Mock()
    rpc = Mock()
    rpc.execute.return_value = Mock(data=updated)
    db.rpc.return_value = rpc
    ctx = _context(db)
    ctx.role = "owner"
    service = Mock()
    service.table.return_value = _query([{}])

    with patch("app.routers.tasks.get_service_client", return_value=service):
        result = reject_task("task-1", "Needs changes", ctx)

    assert result["status"] == "todo"
    assert result["completed_at"] is None
    db.rpc.assert_called_once_with(
        "review_task_approval",
        {"p_task_id": "task-1", "p_decision": "rejected", "p_note": "Needs changes"},
    )


def test_rejected_task_is_editable_for_resubmission():
    current = {
        "id": "task-1",
        "title": "Draft launch",
        "approval_status": "rejected",
        "approval_note": "Needs changes",
    }
    updated = {**current, "title": "Final launch", "status": "todo"}
    db = Mock()
    db.table.side_effect = [_query(current), _query([updated])]
    service = Mock()
    service.table.return_value = _query([{}])

    with patch("app.routers.tasks.get_service_client", return_value=service):
        result = update_task("task-1", TaskUpdate(title="Final launch"), _context(db))

    assert result["title"] == "Final launch"


def test_reviewer_cannot_decide_on_non_pending_task():
    db = Mock()
    db.rpc.return_value.execute.side_effect = RuntimeError("task is not awaiting approval")
    ctx = _context(db)
    ctx.role = "owner"

    with pytest.raises(HTTPException) as exc_info:
        reject_task("task-1", "Needs changes", ctx)

    assert exc_info.value.status_code == 409
    assert exc_info.value.detail["error"]["code"] == "approval_review_failed"


def test_approved_task_is_locked_against_edits():
    db = Mock()
    db.table.return_value = _query({"id": "task-1", "title": "Approved", "approval_status": "approved"})
    with pytest.raises(HTTPException) as exc_info:
        update_task("task-1", TaskUpdate(title="Changed after approval"), _context(db))
    assert exc_info.value.status_code == 409
    assert exc_info.value.detail["error"]["code"] == "approval_locked"


def test_approved_task_is_locked_against_deletion():
    db = Mock()
    query = _query({"id": "task-1", "title": "Approved", "approval_status": "approved"})
    db.table.return_value = query

    with pytest.raises(HTTPException) as exc_info:
        delete_task("task-1", _context(db))

    assert exc_info.value.status_code == 409
    assert exc_info.value.detail["error"]["code"] == "approval_locked"
    query.delete.assert_not_called()


def test_pending_task_must_be_reviewed_before_deletion():
    db = Mock()
    query = _query({"id": "task-1", "title": "Pending", "approval_status": "pending"})
    db.table.return_value = query

    with pytest.raises(HTTPException) as exc_info:
        delete_task("task-1", _context(db))

    assert exc_info.value.status_code == 409
    assert exc_info.value.detail["error"]["code"] == "approval_pending"
    query.delete.assert_not_called()


def test_rejected_task_can_be_edited_but_not_deleted_with_its_history():
    db = Mock()
    query = _query({"id": "task-1", "title": "Rejected", "approval_status": "rejected"})
    db.table.return_value = query

    with pytest.raises(HTTPException) as exc_info:
        delete_task("task-1", _context(db))

    assert exc_info.value.status_code == 409
    assert exc_info.value.detail["error"]["code"] == "approval_history_locked"
    query.delete.assert_not_called()


def test_review_requires_team_plan():
    ctx = _context(Mock())
    ctx.role = "owner"
    ctx.plan = "pro"
    with pytest.raises(HTTPException) as exc_info:
        approve_task("task-1", None, ctx)
    assert exc_info.value.detail["error"]["code"] == "plan_required"
