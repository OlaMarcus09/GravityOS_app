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
    """Queue a personalized team digest once per user on Monday morning."""
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
    workspace_ids = list({workspace_id for memberships in user_workspaces.values() for workspace_id in memberships})
    workspaces = service.table("workspaces").select("id,name").in_("id", workspace_ids).execute().data or []
    workspace_name_by_id = {row["id"]: row.get("name") or "Workspace" for row in workspaces}
    cutoff = now - timedelta(days=8)
    completed = service.table("tasks").select("workspace_id,title,assignee_id,completed_at").eq("status", "done").gte("completed_at", cutoff.isoformat()).execute().data or []
    upcoming = service.table("tasks").select("id,workspace_id,title,assignee_id,due_date").neq("status", "done").gte("due_date", (now.date() - timedelta(days=1)).isoformat()).lte("due_date", (now.date() + timedelta(days=8)).isoformat()).execute().data or []
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
        workspace_sections: list[str] = []
        personal_completed_total = 0
        personal_upcoming_total = 0
        team_completed_total = 0
        team_upcoming_total = 0
        score_delta_total = 0
        for workspace_id in workspace_ids:
            completed_rows = [
                row for row in by_workspace_completed.get(workspace_id, [])
                if row.get("completed_at")
                and (completed_date := _date_in_timezone(row["completed_at"], timezone_name)) is not None
                and local_week_start <= completed_date <= local_today
            ]
            upcoming_rows = [
                row for row in by_workspace_upcoming.get(workspace_id, [])
                if row.get("due_date")
                and local_today <= date.fromisoformat(row["due_date"]) <= local_horizon
            ]
            personal_completed = [row for row in completed_rows if row.get("assignee_id") == user_id]
            personal_upcoming = [row for row in upcoming_rows if row.get("assignee_id") == user_id]
            history = by_workspace_scores.get(workspace_id, [])
            score_delta = 0
            if len(history) >= 2 and history[0].get("overall") is not None and history[-1].get("overall") is not None:
                score_delta = int(history[0]["overall"]) - int(history[-1]["overall"])
            if not completed_rows and not upcoming_rows and not score_delta:
                continue

            personal_completed_total += len(personal_completed)
            personal_upcoming_total += len(personal_upcoming)
            team_completed_total += len(completed_rows)
            team_upcoming_total += len(upcoming_rows)
            score_delta_total += score_delta
            personal_parts = [
                f"you completed {len(personal_completed)} assigned task{'s' if len(personal_completed) != 1 else ''}",
                f"you have {len(personal_upcoming)} assigned task{'s' if len(personal_upcoming) != 1 else ''} due",
            ]
            team_parts = [
                f"the team completed {len(completed_rows)} task{'s' if len(completed_rows) != 1 else ''}",
                f"{len(upcoming_rows)} team task{'s are' if len(upcoming_rows) != 1 else ' is'} due",
            ]
            if score_delta:
                team_parts.append(f"Gravity Score {'rose' if score_delta > 0 else 'fell'} by {abs(score_delta)}")
            workspace_sections.append(
                f"{workspace_name_by_id.get(workspace_id, 'Workspace')}: "
                + "; ".join(personal_parts)
                + ". Team overview: "
                + "; ".join(team_parts)
                + "."
            )
        if not workspace_sections:
            continue
        display_name = profiles_by_id.get(user_id, {}).get("display_name") or "there"
        first_name = display_name.split()[0] if display_name.strip() else "there"
        result = create_notification(
            workspace_id=workspace_ids[0], recipient_id=user_id, kind="weekly_digest",
            title=f"{first_name}, your weekly Gravity OS digest",
            message="Your work and team progress this week:\n\n" + "\n\n".join(workspace_sections),
            action_url="/dashboard",
            metadata={
                "iso_week": f"{week_key.year}-W{week_key.week:02d}",
                "workspace_count": len(workspace_sections),
                "personal_completed": personal_completed_total,
                "personal_upcoming": personal_upcoming_total,
                "team_completed": team_completed_total,
                "team_upcoming": team_upcoming_total,
                "score_delta": score_delta_total,
            },
            dedupe_key=f"weekly-digest:{user_id}:{week_key.year}-W{week_key.week:02d}",
            subject=f"{first_name}, your weekly Gravity OS digest",
            service=service,
        )
        if result.notification_id or result.delivery_id:
            queued += 1
    return queued
