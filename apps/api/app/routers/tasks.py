"""Tasks routes (ARCHITECTURE.md section 3)."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.core.db import get_service_client
from app.core.deps import WorkspaceContext, get_workspace_context, require_writer
from app.schemas.tasks import TaskCreate, TaskOut, TaskUpdate

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
        get_service_client().table("notifications").insert({
            "workspace_id": ctx.workspace_id,
            "recipient_id": assignee_id,
            "kind": "task_assigned",
            "title": "Task assigned to you",
            "message": f'You were assigned to "{task["title"]}".',
            "action_url": "/tasks",
            "metadata": {
                "task_id": task["id"],
                "project_id": task.get("project_id"),
                "assigned_by": ctx.auth.user_id,
            },
        }).execute()
    except Exception:
        # Notification delivery must not roll back the task mutation.
        return


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
            },
        }).execute()
    except Exception:
        # Activity is supporting context and must not block task work.
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
    _get_or_404(ctx, task_id)
    ctx.db.table("tasks").delete().eq("id", task_id).eq("workspace_id", ctx.workspace_id).execute()
