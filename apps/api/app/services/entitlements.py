"""Request-time workspace entitlement view; PostgreSQL enforces the same clock check."""
from __future__ import annotations

from datetime import datetime, timezone


def _future(value: str | None, at: datetime) -> bool:
    if not value:
        return False
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return False
    return parsed.astimezone(timezone.utc) > at


def effective_plan(workspace: dict, *, at: datetime | None = None) -> str:
    at = at or datetime.now(timezone.utc)
    plan = workspace.get("plan", "free")
    billing = workspace.get("billing_status")
    if billing == "manual" and plan in ("pro", "team", "enterprise"):
        return plan
    if billing == "active" and plan in ("pro", "team") and _future(workspace.get("current_period_end"), at):
        return plan
    if plan == "free" and billing == "none" and _future(workspace.get("trial_expires_at"), at):
        started = workspace.get("trial_started_at")
        if started:
            try:
                if datetime.fromisoformat(started.replace("Z", "+00:00")).astimezone(timezone.utc) <= at:
                    return "pro"
            except ValueError:
                pass
    return "free"


def trial_status(workspace: dict, *, at: datetime | None = None) -> str:
    if not workspace.get("trial_started_at"):
        return "none"
    if effective_plan(workspace, at=at) == "pro" and workspace.get("plan") == "free":
        return "active"
    if workspace.get("plan") != "free" or workspace.get("billing_status") != "none":
        return "superseded"
    return "expired"
