"""Tasks routes (ARCHITECTURE.md section 3)."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.core.db import get_service_client
from app.core.deps import WorkspaceContext, get_workspace_context, require_writer
from app.core.tenant_refs import validate_project_reference
from app.schemas.tasks import TaskCreate, TaskUpdate
from app.services.notifications import create_notification

router = APIRouter(prefix="/tasks", tags=["tasks"])


def _validate_assignee(ctx: WorkspaceContext, assignee_id: str) -> None:
    member = (
        ctx.db.table("workspace_members")
        .select("user_id")
        .eq("workspace_id", ctx.workspace_id)
        .eq("user_id", assignee_id)
        .maybe_single()
        .execute()
    )
    if not member or not member.data:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail={
                "error": {
                    "code": "invalid_assignee",
                    "message": "assignee must be a member of this workspace",
                }
            },
        )


def _notify_assignee(ctx: WorkspaceContext, task: dict) -> None:
    assignee_id = task.get("assignee_id")
    if not assignee_id:
        return
    try:
        service = get_service_client()
    except Exception:
        return
    assignment_version = task.get("updated_at") or task.get("created_at") or "created"
    create_notification(
        workspace_id=ctx.workspace_id,
        recipient_id=assignee_id,
        kind="task_assigned",
        title="Task assigned to you",
        message=f'You were assigned to "{task["title"]}".',
        action_url=f"/tasks?task={task['id']}",
        metadata={
            "task_id": task["id"],
            "project_id": task.get("project_id"),
            "assigned_by": ctx.auth.user_id,
        },
        dedupe_key=f"task-assigned:{task['id']}:{assignee_id}:{assignment_version}",
        service=service,
    )


def _record_activity(ctx: WorkspaceContext, task: dict, kind: str) -> None:
    try:
        get_service_client().table("workspace_activity_events").insert({
            "workspace_id": ctx.workspace_id,
            "actor_id": ctx.auth.user_id,
            "event_type": kind,
            "target_type": "task",
            "target_id": task["id"],
            "summary": task["title"],
            "metadata": {
                "project_id": task.get("project_id"),
                "assignee_id": task.get("assignee_id"),
                "status": task.get("status"),
                "approval_status": task.get("approval_status"),
            },
        }).execute()
    except Exception:
        # Activity is supporting context and must not block task work.
        return


def _notify_approval(ctx: WorkspaceContext, task: dict, event: str) -> None:
    try:
        service = get_service_client()
        if event == "submitted":
            reviewers = service.table("workspace_members").select("user_id").eq(
                "workspace_id", ctx.workspace_id
            ).in_("role", ["owner", "admin"]).execute().data or []
            recipient_ids = [row["user_id"] for row in reviewers if row["user_id"] != ctx.auth.user_id]
            title = "Task awaiting approval"
            message = f'"{task["title"]}" is ready for review.'
            kind = "task_approval_requested"
        else:
            recipients = {task.get("approval_submitted_by"), task.get("assignee_id")}
            recipient_ids = [recipient for recipient in recipients if recipient and recipient != ctx.auth.user_id]
            title = f"Task {event}"
            message = (
                f'"{task["title"]}" was approved and completed.'
                if event == "approved"
                else f'"{task["title"]}" was rejected and reopened for changes.'
            )
            kind = f"task_{event}"
        event_version = task.get("approval_reviewed_at") or task.get("updated_at") or event
        for recipient_id in recipient_ids:
            create_notification(
                workspace_id=ctx.workspace_id,
                recipient_id=recipient_id,
                kind=kind,
                title=title,
                message=message,
                action_url=f"/tasks?task={task['id']}",
                metadata={"task_id": task["id"], "actor_id": ctx.auth.user_id},
                dedupe_key=f"task-approval:{event}:{task['id']}:{recipient_id}:{event_version}",
                service=service,
            )
    except Exception:
        return


def _get_or_404(ctx: WorkspaceContext, task_id: str) -> dict:
    row = (
        ctx.db.table("tasks")
        .select("*")
        .eq("id", task_id)
        .eq("workspace_id", ctx.workspace_id)
        .maybe_single()
        .execute()
    )
    if not row.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail={"error": {"code": "not_found", "message": "task not found"}})
    return row.data


@router.get("")
def list_tasks(
    ctx: WorkspaceContext = Depends(get_workspace_context),
    project_id: Optional[str] = Query(None),
    status_filter: Optional[str] = Query(None, alias="status"),
    assignee_id: Optional[str] = Query(None),
    due_before: Optional[str] = Query(None),
) -> list[dict]:
    q = ctx.db.table("tasks").select("*").eq("workspace_id", ctx.workspace_id)
    if project_id:
        q = q.eq("project_id", project_id)
    if status_filter:
        q = q.eq("status", status_filter)
    if assignee_id:
        q = q.eq("assignee_id", assignee_id)
    if due_before:
        q = q.lte("due_date", due_before)
    return q.order("created_at", desc=True).execute().data or []


@router.post("", status_code=status.HTTP_201_CREATED)
def create_task(body: TaskCreate, ctx: WorkspaceContext = Depends(require_writer)) -> dict:
    payload = body.model_dump(exclude_none=True, mode="json")
    if project_id := payload.get("project_id"):
        validate_project_reference(ctx, project_id)
    if assignee_id := payload.get("assignee_id"):
        _validate_assignee(ctx, assignee_id)
    res = (
        ctx.db.table("tasks")
        .insert({**payload, "workspace_id": ctx.workspace_id, "created_by": ctx.auth.user_id})
        .execute()
    )
    task = res.data[0]
    _record_activity(ctx, task, "task_created")
    if task.get("assignee_id"):
        _notify_assignee(ctx, task)
    return task


@router.patch("/{task_id}")
def update_task(task_id: str, body: TaskUpdate, ctx: WorkspaceContext = Depends(require_writer)) -> dict:
    current = _get_or_404(ctx, task_id)
    updates = body.model_dump(exclude_none=True, mode="json")
    if "assignee_id" in body.model_fields_set and body.assignee_id is None:
        updates["assignee_id"] = None
    if not updates:
        return current
    if current.get("approval_status") == "pending":
        raise HTTPException(status_code=409, detail={"error": {"code": "approval_pending", "message": "Resolve the pending review before editing this task"}})
    if current.get("approval_status") == "approved":
        raise HTTPException(status_code=409, detail={"error": {"code": "approval_locked", "message": "Approved tasks are locked until the approval is reset"}})
    if project_id := updates.get("project_id"):
        validate_project_reference(ctx, project_id)
    assignee_changed = (
        "assignee_id" in body.model_fields_set
        and updates.get("assignee_id") != current.get("assignee_id")
    )
    if assignee_changed and updates.get("assignee_id"):
        _validate_assignee(ctx, updates["assignee_id"])
    res = (
        ctx.db.table("tasks")
        .update(updates)
        .eq("id", task_id)
        .eq("workspace_id", ctx.workspace_id)
        .execute()
    )
    task = res.data[0]
    _record_activity(ctx, task, "task_updated")
    if assignee_changed and task.get("assignee_id"):
        _notify_assignee(ctx, task)
    return task


@router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_task(task_id: str, ctx: WorkspaceContext = Depends(require_writer)) -> None:
    current = _get_or_404(ctx, task_id)
    if current.get("approval_status") == "pending":
        raise HTTPException(status_code=409, detail={"error": {"code": "approval_pending", "message": "Resolve the pending review before deleting this task"}})
    if current.get("approval_status") == "approved":
        raise HTTPException(status_code=409, detail={"error": {"code": "approval_locked", "message": "Approved tasks are final records and cannot be deleted"}})
    if current.get("approval_status") == "rejected":
        raise HTTPException(status_code=409, detail={"error": {"code": "approval_history_locked", "message": "Reviewed tasks cannot be deleted because approval history is retained"}})
    ctx.db.table("tasks").delete().eq("id", task_id).eq("workspace_id", ctx.workspace_id).execute()


def _require_reviewer(ctx: WorkspaceContext) -> None:
    if ctx.role not in ("owner", "admin"):
        raise HTTPException(
            status_code=403,
            detail={"error": {"code": "reviewer_required", "message": "Only owners and admins can review tasks"}},
        )


@router.post("/{task_id}/submit-approval")
def submit_task_for_approval(
    task_id: str, ctx: WorkspaceContext = Depends(require_writer)
) -> dict:
    task = _get_or_404(ctx, task_id)
    if ctx.plan != "team":
        raise HTTPException(
            status_code=403,
            detail={"error": {"code": "plan_required", "message": "Approval workflows require the Team plan"}},
        )
    if task.get("approval_status") == "pending":
        return task
    try:
        updated = ctx.db.rpc("submit_task_for_approval", {"p_task_id": task_id}).execute().data
    except Exception as exc:
        raise HTTPException(status_code=403, detail={"error": {"code": "approval_submit_failed", "message": str(exc)}}) from exc
    if isinstance(updated, list):
        updated = updated[0] if updated else None
    if not updated:
        raise HTTPException(
            status_code=404,
            detail={"error": {"code": "not_found", "message": "task not found"}},
        )
    _record_activity(ctx, updated, "task_submitted_for_approval")
    _notify_approval(ctx, updated, "submitted")
    return updated


def _review_task(task_id: str, decision: str, note: Optional[str], ctx: WorkspaceContext) -> dict:
    _require_reviewer(ctx)
    if ctx.plan != "team":
        raise HTTPException(status_code=403, detail={"error": {"code": "plan_required", "message": "Approval workflows require the Team plan"}})
    try:
        updated = ctx.db.rpc("review_task_approval", {"p_task_id": task_id, "p_decision": decision, "p_note": note}).execute().data
    except Exception as exc:
        raise HTTPException(status_code=409, detail={"error": {"code": "approval_review_failed", "message": str(exc)}}) from exc
    if isinstance(updated, list):
        updated = updated[0] if updated else None
    if not updated:
        raise HTTPException(
            status_code=409,
            detail={
                "error": {
                    "code": "approval_review_failed",
                    "message": "Task review failed",
                }
            },
        )
    _record_activity(ctx, updated, f"task_{decision}")
    if decision == "approved":
        _record_activity(ctx, updated, "task_completed")
    _notify_approval(ctx, updated, decision)
    return updated


@router.post("/{task_id}/approve")
def approve_task(
    task_id: str,
    note: Optional[str] = Query(None, max_length=1000),
    ctx: WorkspaceContext = Depends(get_workspace_context),
) -> dict:
    return _review_task(task_id, "approved", note, ctx)


@router.post("/{task_id}/reject")
def reject_task(
    task_id: str,
    note: Optional[str] = Query(None, max_length=1000),
    ctx: WorkspaceContext = Depends(get_workspace_context),
) -> dict:
    return _review_task(task_id, "rejected", note, ctx)
