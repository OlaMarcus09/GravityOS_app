"""Calendar routes (ARCHITECTURE.md section 3)."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.core.deps import WorkspaceContext, get_workspace_context, require_writer
from app.schemas.calendar import CalendarEventCreate, CalendarEventUpdate

router = APIRouter(prefix="/calendar", tags=["calendar"])


def _get_or_404(ctx: WorkspaceContext, event_id: str) -> dict:
    row = (
        ctx.db.table("calendar_events")
        .select("*")
        .eq("id", event_id)
        .eq("workspace_id", ctx.workspace_id)
        .maybe_single()
        .execute()
    )
    if not row.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail={"error": {"code": "not_found", "message": "event not found"}})
    return row.data


@router.get("")
def get_calendar(
    ctx: WorkspaceContext = Depends(get_workspace_context),
    from_: Optional[str] = Query(None, alias="from"),
    to: Optional[str] = Query(None),
) -> dict:
    q = ctx.db.table("calendar_events").select("*").eq("workspace_id", ctx.workspace_id)
    if from_:
        q = q.gte("starts_at", from_)
    if to:
        q = q.lte("starts_at", to)
    events = q.order("starts_at").execute().data or []

    tasks_q = ctx.db.table("tasks").select("id,title,due_date,status").eq("workspace_id", ctx.workspace_id).not_.is_("due_date", "null")
    if from_:
        tasks_q = tasks_q.gte("due_date", from_[:10])
    if to:
        tasks_q = tasks_q.lte("due_date", to[:10])
    tasks = tasks_q.execute().data or []

    projects_q = (
        ctx.db.table("projects")
        .select("id,title,target_release_date,status,type")
        .eq("workspace_id", ctx.workspace_id)
        .not_.is_("target_release_date", "null")
    )
    if from_:
        projects_q = projects_q.gte("target_release_date", from_[:10])
    if to:
        projects_q = projects_q.lte("target_release_date", to[:10])
    project_releases = projects_q.execute().data or []

    # Marketing campaigns with start_date
    campaigns_q = (
        ctx.db.table("campaigns")
        .select("id,name,start_date,end_date,status,objective,project_id")
        .eq("workspace_id", ctx.workspace_id)
        .not_.is_("start_date", "null")
    )
    if from_:
        campaigns_q = campaigns_q.gte("start_date", from_[:10])
    if to:
        campaigns_q = campaigns_q.lte("start_date", to[:10])
    campaigns = campaigns_q.execute().data or []

    # Scheduled content pieces
    content_q = (
        ctx.db.table("content_pieces")
        .select("id,caption,platform,format,scheduled_at,status,campaign_id")
        .eq("workspace_id", ctx.workspace_id)
        .not_.is_("scheduled_at", "null")
    )
    if from_:
        content_q = content_q.gte("scheduled_at", from_)
    if to:
        content_q = content_q.lte("scheduled_at", to)
    scheduled_content = content_q.execute().data or []

    # Release milestones (join via release_plans to scope by workspace)
    milestones_q = (
        ctx.db.table("release_milestones")
        .select("id,title,due_date,status,category,release_plan_id,release_plans!inner(workspace_id,project_id)")
        .eq("release_plans.workspace_id", ctx.workspace_id)
        .not_.is_("due_date", "null")
    )
    if from_:
        milestones_q = milestones_q.gte("due_date", from_[:10])
    if to:
        milestones_q = milestones_q.lte("due_date", to[:10])
    milestones = milestones_q.execute().data or []

    return {
        "events": events,
        "task_due_dates": tasks,
        "project_releases": project_releases,
        "campaigns": campaigns,
        "scheduled_content": scheduled_content,
        "milestones": milestones,
    }


@router.post("/events", status_code=status.HTTP_201_CREATED)
def create_event(body: CalendarEventCreate, ctx: WorkspaceContext = Depends(require_writer)) -> dict:
    res = (
        ctx.db.table("calendar_events")
        .insert({**body.model_dump(exclude_none=True, mode="json"), "workspace_id": ctx.workspace_id})
        .execute()
    )
    return res.data[0]


@router.patch("/events/{event_id}")
def update_event(event_id: str, body: CalendarEventUpdate, ctx: WorkspaceContext = Depends(require_writer)) -> dict:
    _get_or_404(ctx, event_id)
    updates = body.model_dump(exclude_none=True, mode="json")
    if not updates:
        return _get_or_404(ctx, event_id)
    res = (
        ctx.db.table("calendar_events")
        .update(updates)
        .eq("id", event_id)
        .eq("workspace_id", ctx.workspace_id)
        .execute()
    )
    return res.data[0]


@router.delete("/events/{event_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_event(event_id: str, ctx: WorkspaceContext = Depends(require_writer)) -> None:
    _get_or_404(ctx, event_id)
    ctx.db.table("calendar_events").delete().eq("id", event_id).eq("workspace_id", ctx.workspace_id).execute()
