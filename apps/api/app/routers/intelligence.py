"""Gravity Score + AI outputs routes (ARCHITECTURE.md section 2.10/2.11/3).

The Gravity Score is a 0–100 composite computed from six dimensions:
  - Consistency: regular task completion + calendar activity
  - Organization: tasks structured with projects, due dates, priorities
  - Execution: task completion rate + milestone completion
  - Marketing: campaigns created + content scheduled
  - Collaboration: workspace members + role diversity (Team plan)
  - Business Readiness: budgets, catalogue items, release plans

POST /gravity-score/compute triggers a fresh calculation and stores it.
GET  /gravity-score returns the latest snapshot.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Query

from app.core.db import get_service_client
from app.core.deps import WorkspaceContext, get_workspace_context

router = APIRouter(tags=["intelligence"])


def _clamp(val: float, lo: float = 0, hi: float = 100) -> int:
    return max(int(lo), min(int(hi), int(round(val))))


def _compute_score(ctx: WorkspaceContext) -> dict:
    """Calculate all six Gravity Score dimensions from live data."""
    ws = ctx.workspace_id
    today = date.today()
    thirty_days_ago = (today - timedelta(days=30)).isoformat()

    # ---------- fetch raw data ----------

    all_tasks = (
        ctx.db.table("tasks").select("id,status,due_date,priority,project_id,completed_at,created_at")
        .eq("workspace_id", ws).execute().data or []
    )
    recent_tasks = [t for t in all_tasks if (t.get("created_at") or "") >= thirty_days_ago]

    all_events = (
        ctx.db.table("calendar_events").select("id,starts_at")
        .eq("workspace_id", ws).gte("starts_at", thirty_days_ago).execute().data or []
    )

    projects = (
        ctx.db.table("projects").select("id,status,target_release_date")
        .eq("workspace_id", ws).execute().data or []
    )

    release_plans = (
        ctx.db.table("release_plans").select("id,status")
        .eq("workspace_id", ws).execute().data or []
    )

    milestones = (
        ctx.db.table("release_milestones")
        .select("id,status,release_plan_id,release_plans!inner(workspace_id)")
        .eq("release_plans.workspace_id", ws).execute().data or []
    )

    campaigns = (
        ctx.db.table("campaigns").select("id,status")
        .eq("workspace_id", ws).execute().data or []
    )

    content = (
        ctx.db.table("content_pieces").select("id,status,scheduled_at")
        .eq("workspace_id", ws).execute().data or []
    )

    members = (
        ctx.db.table("workspace_members").select("user_id,role")
        .eq("workspace_id", ws).execute().data or []
    )

    budgets = (
        ctx.db.table("budgets").select("id")
        .eq("workspace_id", ws).execute().data or []
    )

    catalogue = (
        ctx.db.table("catalogue_items").select("id")
        .eq("workspace_id", ws).execute().data or []
    )

    # ---------- 1. Consistency (regular activity) ----------
    # Tasks completed in last 30 days + calendar events booked
    done_recent = len([t for t in recent_tasks if t.get("status") == "done"])
    event_count = len(all_events)
    # Score: up to 50 from tasks (10 done = 50), up to 50 from events (10 events = 50)
    consistency = _clamp((min(done_recent, 10) / 10) * 50 + (min(event_count, 10) / 10) * 50)

    # ---------- 2. Organization ----------
    # % of tasks with due dates + % linked to projects + % with priority set
    total_tasks = len(all_tasks)
    if total_tasks > 0:
        has_due = len([t for t in all_tasks if t.get("due_date")])
        has_project = len([t for t in all_tasks if t.get("project_id")])
        has_priority = len([t for t in all_tasks if t.get("priority") and t["priority"] != "low"])
        organization = _clamp(
            (has_due / total_tasks) * 40 +
            (has_project / total_tasks) * 35 +
            (has_priority / total_tasks) * 25
        )
    else:
        organization = 0

    # ---------- 3. Execution ----------
    # Task completion rate + milestone completion rate
    done_all = len([t for t in all_tasks if t.get("status") == "done"])
    task_rate = (done_all / total_tasks * 100) if total_tasks > 0 else 0

    total_milestones = len(milestones)
    done_milestones = len([m for m in milestones if m.get("status") == "done"])
    milestone_rate = (done_milestones / total_milestones * 100) if total_milestones > 0 else 0

    if total_milestones > 0:
        execution = _clamp(task_rate * 0.6 + milestone_rate * 0.4)
    else:
        execution = _clamp(task_rate)

    # ---------- 4. Marketing ----------
    # Campaigns + content pieces (especially scheduled/published)
    total_campaigns = len(campaigns)
    active_campaigns = len([c for c in campaigns if c.get("status") in ("active", "completed")])
    total_content = len(content)
    scheduled_content = len([c for c in content if c.get("status") in ("scheduled", "published")])

    if total_campaigns == 0 and total_content == 0:
        marketing = 0
    else:
        camp_score = min(total_campaigns, 5) / 5 * 40 + (active_campaigns / max(total_campaigns, 1)) * 10
        content_score = min(total_content, 20) / 20 * 30 + (scheduled_content / max(total_content, 1)) * 20
        marketing = _clamp(camp_score + content_score)

    # ---------- 5. Collaboration ----------
    # Number of members + role diversity
    member_count = len(members)
    unique_roles = len(set(m.get("role") for m in members))
    if member_count <= 1:
        collaboration = 20  # Solo — baseline
    else:
        collaboration = _clamp(
            min(member_count, 8) / 8 * 60 +
            min(unique_roles, 4) / 4 * 40
        )

    # ---------- 6. Business Readiness ----------
    # Has budgets + catalogue items + release plans + projects with release dates
    has_budgets = min(len(budgets), 3) / 3
    has_catalogue = min(len(catalogue), 10) / 10
    has_plans = min(len(release_plans), 3) / 3
    dated_projects = len([p for p in projects if p.get("target_release_date")])
    has_dated = min(dated_projects, 3) / 3
    business_readiness = _clamp(
        has_budgets * 25 + has_catalogue * 25 + has_plans * 25 + has_dated * 25
    )

    # ---------- Overall ----------
    overall = _clamp(
        consistency * 0.20 +
        organization * 0.15 +
        execution * 0.25 +
        marketing * 0.15 +
        collaboration * 0.10 +
        business_readiness * 0.15
    )

    return {
        "overall": overall,
        "consistency": consistency,
        "organization": organization,
        "execution": execution,
        "marketing": marketing,
        "collaboration": collaboration,
        "business_readiness": business_readiness,
    }


@router.get("/gravity-score")
def get_gravity_score(ctx: WorkspaceContext = Depends(get_workspace_context)) -> Optional[dict]:
    rows = (
        ctx.db.table("gravity_scores").select("*")
        .eq("workspace_id", ctx.workspace_id).order("computed_at", desc=True).limit(1).execute().data or []
    )
    return rows[0] if rows else None


@router.post("/gravity-score/compute")
def compute_gravity_score(ctx: WorkspaceContext = Depends(get_workspace_context)) -> dict:
    """Calculate and store a fresh Gravity Score snapshot."""
    scores = _compute_score(ctx)
    row = {
        "workspace_id": ctx.workspace_id,
        "computed_at": datetime.now(timezone.utc).isoformat(),
        **scores,
    }
    # Scores are service-owned snapshots. Inputs are read through the caller's
    # RLS-scoped client above; only the final snapshot write uses the service
    # client because RLS intentionally exposes gravity_scores as read-only.
    res = get_service_client().table("gravity_scores").insert(row).execute()
    return res.data[0]


@router.get("/ai/outputs")
def list_ai_outputs(
    ctx: WorkspaceContext = Depends(get_workspace_context),
    kind: Optional[str] = Query(None),
) -> list[dict]:
    q = ctx.db.table("ai_outputs").select("*").eq("workspace_id", ctx.workspace_id)
    if kind:
        q = q.eq("kind", kind)
    return q.order("generated_at", desc=True).execute().data or []
