"""Deadline reminder generation and Resend outbox delivery jobs."""

from __future__ import annotations

import json
from datetime import date, datetime, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from app.core.db import get_service_client
from app.integrations.resend import ResendClient, render_notification_email
from app.services.notifications import create_notification


def _local_date(timezone_name: str, now: datetime) -> date:
    try:
        return now.astimezone(ZoneInfo(timezone_name)).date()
    except ZoneInfoNotFoundError:
        return now.astimezone(timezone.utc).date()


def generate_deadline_reminders(
    *,
    service: Any | None = None,
    now: datetime | None = None,
) -> int:
    """Queue each assignee's configured 3/1/0-day reminders exactly once."""
    service = service or get_service_client()
    now = now or datetime.now(timezone.utc)
    preferences = (
        service.table("notification_preferences")
        .select("user_id,email_enabled,in_app_enabled,deadline_reminders,reminder_days_before")
        .execute()
        .data
        or []
    )
    preference_by_user = {row["user_id"]: row for row in preferences}

    maximum_days = max(
        (day for row in preferences for day in row.get("reminder_days_before", [3, 1, 0]) if day >= 0),
        default=3,
    )
    utc_today = now.astimezone(timezone.utc).date()
    tasks = (
        service.table("tasks")
        .select("id,workspace_id,title,due_date,assignee_id,status")
        .not_.is_("assignee_id", "null")
        .neq("status", "done")
        # Include the previous UTC date for users west of UTC whose local day
        # has not rolled over yet; exact matching happens below in user time.
        .gte("due_date", (utc_today - timedelta(days=1)).isoformat())
        .lte("due_date", (utc_today + timedelta(days=maximum_days + 1)).isoformat())
        .execute()
        .data
        or []
    )
    assignee_ids = list({task["assignee_id"] for task in tasks if task.get("assignee_id")})
    profiles = []
    if assignee_ids:
        profiles = (
            service.table("profiles")
            .select("id,timezone")
            .in_("id", assignee_ids)
            .execute()
            .data
            or []
        )
    timezone_by_user = {profile["id"]: profile.get("timezone") or "UTC" for profile in profiles}
    queued = 0
    for task in tasks:
        preference = preference_by_user.get(task.get("assignee_id"), {})
        if not preference.get("deadline_reminders", True):
            continue
        due_date = date.fromisoformat(task["due_date"])
        timezone_name = timezone_by_user.get(task["assignee_id"], "UTC")
        days_before = (due_date - _local_date(timezone_name, now)).days
        if days_before not in preference.get("reminder_days_before", [3, 1, 0]):
            continue
        timing = "due today" if days_before == 0 else f"due in {days_before} day{'s' if days_before != 1 else ''}"
        result = create_notification(
            workspace_id=task["workspace_id"],
            recipient_id=task["assignee_id"],
            kind="task_deadline_reminder",
            title=f"Task {timing}",
            message=f'"{task["title"]}" is {timing}.',
            action_url=f"/tasks?task={task['id']}",
            metadata={"task_id": task["id"], "due_date": task["due_date"], "days_before": days_before},
            dedupe_key=(
                f"task-deadline:{task['id']}:{task['assignee_id']}:"
                f"{task['due_date']}:{days_before}"
            ),
            service=service,
        )
        if result.notification_id or result.delivery_id:
            queued += 1
    return queued


def _retry_at(now: datetime, attempts: int) -> str:
    delay_minutes = min(5 * (2 ** max(attempts - 1, 0)), 24 * 60)
    return (now + timedelta(minutes=delay_minutes)).isoformat()


def deliver_pending_emails(
    *,
    service: Any | None = None,
    resend: ResendClient | None = None,
    now: datetime | None = None,
    limit: int = 50,
) -> dict[str, int]:
    """Claim due outbox rows, deliver with idempotency, and schedule retries."""
    service = service or get_service_client()
    now = now or datetime.now(timezone.utc)
    resend = resend or ResendClient()
    rows = (
        service.table("email_deliveries")
        .select("*")
        .in_("status", ["pending", "failed"])
        .lte("next_attempt_at", now.isoformat())
        .order("created_at")
        .limit(limit)
        .execute()
        .data
        or []
    )
    sent = failed = 0
    for row in rows:
        attempts = int(row.get("attempts", 0)) + 1
        claimed = (
            service.table("email_deliveries")
            .update({"status": "processing", "attempts": attempts, "last_error": None})
            .eq("id", row["id"])
            .in_("status", ["pending", "failed"])
            .eq("attempts", row.get("attempts", 0))
            .lte("next_attempt_at", now.isoformat())
            .execute()
            .data
            or []
        )
        if not claimed:
            continue
        data = row.get("template_data") or {}
        try:
            email = render_notification_email(
                subject=row["subject"],
                title=data.get("title", row["subject"]),
                message=data.get("message", "You have a new Gravity OS notification."),
                action_url=data.get("action_url"),
                action_label=data.get("action_label", "Open Gravity OS"),
            )
            provider_id = resend.send_email(
                recipient=row["recipient_email"],
                email=email,
                idempotency_key=row["idempotency_key"],
            )
            service.table("email_deliveries").update(
                {
                    "status": "sent",
                    "provider_message_id": provider_id,
                    "sent_at": now.isoformat(),
                    "last_error": None,
                }
            ).eq("id", row["id"]).eq("status", "processing").execute()
            if row.get("notification_id"):
                service.table("notifications").update({"emailed_at": now.isoformat()}).eq(
                    "id", row["notification_id"]
                ).execute()
            sent += 1
        except Exception as exc:
            exhausted = attempts >= int(row.get("max_attempts", 5))
            service.table("email_deliveries").update(
                {
                    "status": "cancelled" if exhausted else "failed",
                    "next_attempt_at": _retry_at(now, attempts),
                    "last_error": str(exc)[:1000],
                }
            ).eq("id", row["id"]).eq("status", "processing").execute()
            failed += 1
    return {"sent": sent, "failed": failed}


def run_notification_cycle() -> dict[str, int]:
    """Generate reminders and drain the due email outbox for cron execution."""
    service = get_service_client()
    queued = generate_deadline_reminders(service=service)
    with ResendClient() as resend:
        delivered = deliver_pending_emails(service=service, resend=resend)
    return {"queued": queued, **delivered}


def main() -> None:
    print(json.dumps(run_notification_cycle(), sort_keys=True))


if __name__ == "__main__":
    main()
