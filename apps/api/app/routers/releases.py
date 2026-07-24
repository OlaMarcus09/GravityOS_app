"""Release planner routes (ARCHITECTURE.md section 3)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from app.core.deps import WorkspaceContext, get_workspace_context, require_pro
from app.schemas.releases import MilestoneCreate, MilestoneUpdate, ReleasePlanCreate, ReleasePlanUpdate

router = APIRouter(tags=["releases"])


def _get_plan_or_404(ctx: WorkspaceContext, plan_id: str) -> dict:
    row = ctx.db.table("release_plans").select("*").eq("id", plan_id).eq("workspace_id", ctx.workspace_id).maybe_single().execute()
    if not row.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail={"error": {"code": "not_found", "message": "release plan not found"}})
    return row.data


def _get_milestone_or_404(ctx: WorkspaceContext, milestone_id: str) -> dict:
    row = (
        ctx.db.table("release_milestones")
        .select("*, release_plans!inner(workspace_id)")
        .eq("id", milestone_id)
        .eq("release_plans.workspace_id", ctx.workspace_id)
        .maybe_single()
        .execute()
    )
    if not row.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail={"error": {"code": "not_found", "message": "milestone not found"}})
    return row.data


@router.get("/projects/{project_id}/release-plan")
def get_release_plan(project_id: str, ctx: WorkspaceContext = Depends(get_workspace_context)) -> dict:
    row = (
        ctx.db.table("release_plans")
        .select("*, release_milestones(*)")
        .eq("project_id", project_id)
        .eq("workspace_id", ctx.workspace_id)
        .maybe_single()
        .execute()
    )
    if not row.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail={"error": {"code": "not_found", "message": "release plan not found"}})
    return row.data


@router.post("/projects/{project_id}/release-plan", status_code=status.HTTP_201_CREATED)
def create_release_plan(project_id: str, body: ReleasePlanCreate, ctx: WorkspaceContext = Depends(require_pro)) -> dict:
    res = ctx.db.table("release_plans").insert({
        **body.model_dump(mode="json"),
        "project_id": project_id,
        "workspace_id": ctx.workspace_id,
    }).execute()
    return res.data[0]


@router.patch("/release-plans/{plan_id}")
def update_release_plan(plan_id: str, body: ReleasePlanUpdate, ctx: WorkspaceContext = Depends(require_pro)) -> dict:
    _get_plan_or_404(ctx, plan_id)
    updates = body.model_dump(exclude_none=True, mode="json")
    if not updates:
        return _get_plan_or_404(ctx, plan_id)
    return ctx.db.table("release_plans").update(updates).eq("id", plan_id).eq("workspace_id", ctx.workspace_id).execute().data[0]


@router.post("/release-plans/{plan_id}/milestones", status_code=status.HTTP_201_CREATED)
def add_milestone(plan_id: str, body: MilestoneCreate, ctx: WorkspaceContext = Depends(require_pro)) -> dict:
    _get_plan_or_404(ctx, plan_id)
    res = ctx.db.table("release_milestones").insert({**body.model_dump(exclude_none=True, mode="json"), "release_plan_id": plan_id}).execute()
    return res.data[0]


@router.patch("/milestones/{milestone_id}")
def update_milestone(milestone_id: str, body: MilestoneUpdate, ctx: WorkspaceContext = Depends(require_pro)) -> dict:
    _get_milestone_or_404(ctx, milestone_id)
    updates = body.model_dump(exclude_none=True, mode="json")
    if not updates:
        return _get_milestone_or_404(ctx, milestone_id)
    return ctx.db.table("release_milestones").update(updates).eq("id", milestone_id).execute().data[0]


@router.delete("/milestones/{milestone_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_milestone(milestone_id: str, ctx: WorkspaceContext = Depends(require_pro)) -> None:
    _get_milestone_or_404(ctx, milestone_id)
    ctx.db.table("release_milestones").delete().eq("id", milestone_id).execute()
