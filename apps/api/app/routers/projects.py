"""Projects routes (ARCHITECTURE.md section 3)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from app.core.deps import (
    PLAN_LIMITS,
    WorkspaceContext,
    enforce_plan_limit,
    get_workspace_context,
    require_writer,
)
from app.schemas.projects import ProjectCreate, ProjectOut, ProjectUpdate

router = APIRouter(prefix="/projects", tags=["projects"])

_ACTIVE_STATUSES = ("idea", "in_progress", "ready", "released")


def _get_or_404(ctx: WorkspaceContext, project_id: str) -> dict:
    row = (
        ctx.db.table("projects")
        .select("*")
        .eq("id", project_id)
        .eq("workspace_id", ctx.workspace_id)
        .maybe_single()
        .execute()
    )
    if not row.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail={"error": {"code": "not_found", "message": "project not found"}})
    return row.data


@router.get("")
def list_projects(ctx: WorkspaceContext = Depends(get_workspace_context)) -> list[dict]:
    res = (
        ctx.db.table("projects")
        .select("*")
        .eq("workspace_id", ctx.workspace_id)
        .order("created_at", desc=True)
        .execute()
    )
    return res.data or []


@router.post("", status_code=status.HTTP_201_CREATED)
def create_project(
    body: ProjectCreate,
    ctx: WorkspaceContext = Depends(enforce_plan_limit("active_projects")),
) -> dict:
    limit = PLAN_LIMITS.get(ctx.plan, {}).get("active_projects")
    if limit is not None:
        count_res = (
            ctx.db.table("projects")
            .select("id", count="exact")
            .eq("workspace_id", ctx.workspace_id)
            .in_("status", list(_ACTIVE_STATUSES))
            .execute()
        )
        if (count_res.count or 0) >= limit:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"error": {"code": "plan_limit", "message": f"free plan allows {limit} active project(s)"}},
            )
    res = (
        ctx.db.table("projects")
        .insert({**body.model_dump(exclude_none=True), "workspace_id": ctx.workspace_id, "created_by": ctx.auth.user_id})
        .execute()
    )
    return res.data[0]


@router.get("/{project_id}")
def get_project(project_id: str, ctx: WorkspaceContext = Depends(get_workspace_context)) -> dict:
    return _get_or_404(ctx, project_id)


@router.patch("/{project_id}")
def update_project(
    project_id: str,
    body: ProjectUpdate,
    ctx: WorkspaceContext = Depends(require_writer),
) -> dict:
    _get_or_404(ctx, project_id)
    updates = body.model_dump(exclude_none=True)
    if not updates:
        return _get_or_404(ctx, project_id)
    res = (
        ctx.db.table("projects")
        .update(updates)
        .eq("id", project_id)
        .eq("workspace_id", ctx.workspace_id)
        .execute()
    )
    return res.data[0]


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_project(project_id: str, ctx: WorkspaceContext = Depends(require_writer)) -> None:
    _get_or_404(ctx, project_id)
    ctx.db.table("projects").delete().eq("id", project_id).eq("workspace_id", ctx.workspace_id).execute()
