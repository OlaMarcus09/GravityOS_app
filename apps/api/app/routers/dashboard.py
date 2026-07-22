"""Dashboard aggregation route (ARCHITECTURE.md section 2.9 / 3). Skeleton stub.

No table of its own — reads across tasks, calendar, release milestones, and the
latest gravity score / AI summary into a single "today" view.
"""
from __future__ import annotations

from datetime import date, timedelta

from fastapi import APIRouter, Depends

from app.core.deps import WorkspaceContext, get_workspace_context

router = APIRouter(tags=["dashboard"])


@router.get("/dashboard")
def get_dashboard(ctx: WorkspaceContext = Depends(get_workspace_context)) -> dict:
    ws = ctx.workspace_id
    today = date.today().isoformat()
    soon = (date.today() + timedelta(days=7)).isoformat()

    due_today = (
        ctx.db.table("tasks").select("id,title,status,due_date,priority")
        .eq("workspace_id", ws).eq("due_date", today).neq("status", "done").execute().data or []
    )
    overdue = (
        ctx.db.table("tasks").select("id,title,status,due_date,priority")
        .eq("workspace_id", ws).lt("due_date", today).neq("status", "done").execute().data or []
    )
    upcoming_events = (
        ctx.db.table("calendar_events").select("id,title,type,starts_at")
        .eq("workspace_id", ws).gte("starts_at", today).order("starts_at").limit(10).execute().data or []
    )
    upcoming_milestones = (
        ctx.db.table("release_milestones")
        .select("id,title,due_date,status,release_plans!inner(workspace_id)")
        .eq("release_plans.workspace_id", ws).eq("status", "pending")
        .gte("due_date", today).lte("due_date", soon).order("due_date").execute().data or []
    )
    latest_score = (
        ctx.db.table("gravity_scores").select("*")
        .eq("workspace_id", ws).order("computed_at", desc=True).limit(1).execute().data or []
    )
    latest_ai = (
        ctx.db.table("ai_outputs").select("*")
        .eq("workspace_id", ws).order("generated_at", desc=True).limit(1).execute().data or []
    )
    project_count = (
        ctx.db.table("projects").select("id", count="exact")
        .eq("workspace_id", ws).execute().count or 0
    )
    task_count = (
        ctx.db.table("tasks").select("id", count="exact")
        .eq("workspace_id", ws).execute().count or 0
    )
    catalogue_count = (
        ctx.db.table("catalogue_items").select("id", count="exact")
        .eq("workspace_id", ws).execute().count or 0
    )
    has_release_plan = bool(
        ctx.db.table("release_plans").select("id")
        .eq("workspace_id", ws).limit(1).execute().data
    )

    return {
        "tasks_due_today": due_today,
        "tasks_overdue": overdue,
        "upcoming_events": upcoming_events,
        "upcoming_milestones": upcoming_milestones,
        "gravity_score": latest_score[0] if latest_score else None,
        "latest_ai_output": latest_ai[0] if latest_ai else None,
        "project_count": project_count,
        "task_count": task_count,
        "catalogue_count": catalogue_count,
        "has_release_plan": has_release_plan,
    }
