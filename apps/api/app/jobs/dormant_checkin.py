"""Contextual, bounded check-ins for users who have gone quiet."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from app.core.db import get_service_client
from app.services.notifications import create_notification

DORMANT_DAYS = 7


def generate_dormant_checkins(*, service: Any | None = None, now: datetime | None = None) -> int:
    service = service or get_service_client()
    now = now or datetime.now(timezone.utc)
    users = service.auth.admin.list_users()
    user_rows = getattr(users, "users", users) or []
    if isinstance(user_rows, dict):
        user_rows = user_rows.get("users", [])
    members = service.table("workspace_members").select("workspace_id,user_id").execute().data or []
    workspace_by_user: dict[str, str] = {}
    for member in members:
        workspace_by_user.setdefault(member["user_id"], member["workspace_id"])
    activity = service.table("workspace_activity_events").select("actor_id,summary,created_at").order("created_at", desc=True).execute().data or []
    latest_by_user: dict[str, dict] = {}
    for row in activity:
        actor_id = row.get("actor_id")
        if actor_id and actor_id not in latest_by_user:
            latest_by_user[actor_id] = row
    cutoff = now - timedelta(days=DORMANT_DAYS)
    queued = 0
    for user in user_rows:
        user_id = getattr(user, "id", None) or (user.get("id") if isinstance(user, dict) else None)
        last_sign_in = getattr(user, "last_sign_in_at", None) or (user.get("last_sign_in_at") if isinstance(user, dict) else None)
        if not user_id or not last_sign_in or user_id not in latest_by_user:
            continue
        try:
            last_login = datetime.fromisoformat(str(last_sign_in).replace("Z", "+00:00"))
            event_at = datetime.fromisoformat(str(latest_by_user[user_id]["created_at"]).replace("Z", "+00:00"))
        except (KeyError, ValueError):
            continue
        if last_login.tzinfo is None:
            last_login = last_login.replace(tzinfo=timezone.utc)
        if event_at.tzinfo is None:
            event_at = event_at.replace(tzinfo=timezone.utc)
        last_active = max(last_login, event_at)
        if last_active >= cutoff:
            continue
        workspace_id = workspace_by_user.get(user_id)
        if not workspace_id:
            continue
        period_started = last_active.isoformat()
        dedupe_key = f"dormant-checkin:{user_id}:{period_started}"
        existing = (
            service.table("retention_checkins")
            .select("id")
            .eq("dedupe_key", dedupe_key)
            .limit(1)
            .execute()
            .data
            or []
        )
        if existing:
            continue
        result = create_notification(
            workspace_id=workspace_id, recipient_id=user_id, kind="dormant_checkin",
            title="Your Gravity workspace is ready when you are",
            message=f"You last worked on {latest_by_user[user_id].get('summary') or 'your workspace'}. Pick up where you left off when you are ready.",
            action_url="/dashboard", metadata={"last_activity_at": period_started, "last_activity": latest_by_user[user_id].get("summary")},
            dedupe_key=dedupe_key, subject="A quick Gravity OS check-in", service=service,
        )
        if not (result.notification_id or result.delivery_id):
            continue
        try:
            service.table("retention_checkins").insert({"user_id": user_id, "kind": "dormant_checkin", "period_started_at": period_started, "dedupe_key": dedupe_key}).execute()
        except Exception:
            pass
        queued += 1
    return queued
