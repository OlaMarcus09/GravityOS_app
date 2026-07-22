"""Tasks routes (ARCHITECTURE.md section 3)."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.core.deps import WorkspaceContext, get_workspace_context, require_writer
from app.schemas.tasks import TaskCreate, TaskOut, TaskUpdate

router = APIRouter(prefix="/tasks", tags=["tasks"])


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
    res = (
        ctx.db.table("tasks")
        .insert({**payload, "workspace_id": ctx.workspace_id, "created_by": ctx.auth.user_id})
        .execute()
    )
    return res.data[0]


@router.patch("/{task_id}")
def update_task(task_id: str, body: TaskUpdate, ctx: WorkspaceContext = Depends(require_writer)) -> dict:
    _get_or_404(ctx, task_id)
    updates = body.model_dump(exclude_none=True, mode="json")
    if not updates:
        return _get_or_404(ctx, task_id)
    res = (
        ctx.db.table("tasks")
        .update(updates)
        .eq("id", task_id)
        .eq("workspace_id", ctx.workspace_id)
        .execute()
    )
    return res.data[0]


@router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_task(task_id: str, ctx: WorkspaceContext = Depends(require_writer)) -> None:
    _get_or_404(ctx, task_id)
    ctx.db.table("tasks").delete().eq("id", task_id).eq("workspace_id", ctx.workspace_id).execute()
