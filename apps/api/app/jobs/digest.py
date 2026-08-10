"""Weekly, non-empty workspace summaries."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from app.core.db import get_service_client
from app.services.notifications import create_notification


def _local_date(timezone_name: str, now: datetime) -> date:
    try:
        return now.astimezone(ZoneInfo(timezone_name or "UTC")).date()
    except ZoneInfoNotFoundError:
        return now.astimezone(timezone.utc).date()


def _local_hour(timezone_name: str, now: datetime) -> int:
    try:
        return now.astimezone(ZoneInfo(timezone_name or "UTC")).hour
    except ZoneInfoNotFoundError:
        return now.astimezone(timezone.utc).hour


def _date_in_timezone(value: str, timezone_name: str) -> date | None:
    try:
        captured = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if captured.tzinfo is None:
            captured = captured.replace(tzinfo=timezone.utc)
        try:
            return captured.astimezone(ZoneInfo(timezone_name or "UTC")).date()
        except ZoneInfoNotFoundError:
            return captured.astimezone(timezone.utc).date()
    except ValueError:
        return None


def generate_weekly_digests(*, service: Any | None = None, now: datetime | None = None) -> int:
    """Queue a useful digest once per user, during their Monday 09:00 hour."""
    service = service or get_service_client()
    now = now or datetime.now(timezone.utc)
    preferences = service.table("notification_preferences").select("*").execute().data or []
    preference_by_user = {row["user_id"]: row for row in preferences}
    members = service.table("workspace_members").select("workspace_id,user_id").execute().data or []
    user_workspaces: dict[str, list[str]] = {}
    for member in members:
        user_workspaces.setdefault(member["user_id"], []).append(member["workspace_id"])
    user_ids = list(user_workspaces)
    if not user_ids:
        return 0
    profiles = service.table("profiles").select("id,display_name,timezone").in_("id", user_ids).execute().data or []
    profiles_by_id = {row["id"]: row for row in profiles}
    cutoff = now - timedelta(days=8)
    completed = service.table("tasks").select("workspace_id,title,completed_at").eq("status", "done").gte("completed_at", cutoff.isoformat()).execute().data or []
    upcoming = service.table("tasks").select("id,workspace_id,title,due_date").neq("status", "done").gte("due_date", (now.date() - timedelta(days=1)).isoformat()).lte("due_date", (now.date() + timedelta(days=8)).isoformat()).execute().data or []
    scores = service.table("gravity_scores").select("workspace_id,overall,computed_at").gte("computed_at", (now - timedelta(days=8)).isoformat()).order("computed_at", desc=True).execute().data or []
    by_workspace_completed: dict[str, list[dict]] = {}
    by_workspace_upcoming: dict[str, list[dict]] = {}
    by_workspace_scores: dict[str, list[dict]] = {}
    for row in completed:
        by_workspace_completed.setdefault(row["workspace_id"], []).append(row)
    for row in upcoming:
        by_workspace_upcoming.setdefault(row["workspace_id"], []).append(row)
    for row in scores:
        by_workspace_scores.setdefault(row["workspace_id"], []).append(row)
    queued = 0
    for user_id, workspace_ids in user_workspaces.items():
        preference = preference_by_user.get(user_id, {})
        if not preference.get("weekly_digests", True) or not (preference.get("in_app_enabled", True) or preference.get("email_enabled", True)):
            continue
        timezone_name = profiles_by_id.get(user_id, {}).get("timezone") or "UTC"
        local_now = now.astimezone(timezone.utc)
        try:
            local_now = now.astimezone(ZoneInfo(timezone_name))
        except ZoneInfoNotFoundError:
            pass
        if local_now.weekday() != 0 or _local_hour(timezone_name, now) != 9:
            continue
        week_key = local_now.date().isocalendar()
        local_today = _local_date(timezone_name, now)
        local_week_start = local_today - timedelta(days=7)
        local_horizon = local_today + timedelta(days=7)
        completed_rows = [
            row
            for ws in workspace_ids
            for row in by_workspace_completed.get(ws, [])
            if row.get("completed_at")
            and (completed_date := _date_in_timezone(row["completed_at"], timezone_name)) is not None
            and local_week_start <= completed_date <= local_today
        ]
        upcoming_rows = [
            row
            for ws in workspace_ids
            for row in by_workspace_upcoming.get(ws, [])
            if row.get("due_date")
            and local_today <= date.fromisoformat(row["due_date"]) <= local_horizon
        ]
        score_deltas: list[int] = []
        for ws in workspace_ids:
            history = by_workspace_scores.get(ws, [])
            if len(history) >= 2 and history[0].get("overall") is not None and history[-1].get("overall") is not None:
                delta = int(history[0]["overall"]) - int(history[-1]["overall"])
                if delta:
                    score_deltas.append(delta)
        if not completed_rows and not upcoming_rows and not score_deltas:
            continue
        sections = []
        if completed_rows:
            sections.append(f"{len(completed_rows)} task{'s' if len(completed_rows) != 1 else ''} completed")
        if upcoming_rows:
            sections.append(f"{len(upcoming_rows)} task{'s' if len(upcoming_rows) != 1 else ''} due in the next 7 days")
        if score_deltas:
            delta = sum(score_deltas)
            sections.append(f"Gravity Score {'rose' if delta > 0 else 'fell'} by {abs(delta)}")
        result = create_notification(
            workspace_id=workspace_ids[0], recipient_id=user_id, kind="weekly_digest",
            title="Your weekly Gravity OS digest", message="This week: " + "; ".join(sections) + ".",
            action_url="/dashboard", metadata={"iso_week": f"{week_key.year}-W{week_key.week:02d}", "completed": len(completed_rows), "upcoming": len(upcoming_rows), "score_delta": sum(score_deltas) if score_deltas else 0},
            dedupe_key=f"weekly-digest:{user_id}:{week_key.year}-W{week_key.week:02d}", subject="Your weekly Gravity OS digest", service=service,
        )
        if result.notification_id or result.delivery_id:
            queued += 1
    return queued
