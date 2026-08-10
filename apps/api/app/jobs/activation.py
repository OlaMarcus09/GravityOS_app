"""Gentle first-action nudges for newly provisioned, still-empty workspaces."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from app.core.db import get_service_client
from app.services.notifications import create_notification

ACTIVATION_TITLE = "Give your workspace a first win"
ACTIVATION_MESSAGE = (
    "Your Gravity workspace is ready. Create your first project to give your "
    "next release, campaign, or idea a home."
)


def generate_activation_nudges(*, service: Any | None = None, now: datetime | None = None) -> int:
    """Queue one concrete first-project prompt for each eligible workspace owner."""
    service = service or get_service_client()
    now = now or datetime.now(timezone.utc)
    lower = (now - timedelta(hours=48)).isoformat()
    upper = (now - timedelta(hours=24)).isoformat()
    workspaces = (
        service.table("workspaces")
        .select("id,owner_id,created_at")
        .gte("created_at", lower)
        .lte("created_at", upper)
        .execute()
        .data
        or []
    )
    if not workspaces:
        return 0
    workspace_ids = [row["id"] for row in workspaces]
    projects = service.table("projects").select("workspace_id").in_("workspace_id", workspace_ids).execute().data or []
    tasks = service.table("tasks").select("workspace_id").in_("workspace_id", workspace_ids).execute().data or []
    project_count = {workspace_id: 0 for workspace_id in workspace_ids}
    task_count = {workspace_id: 0 for workspace_id in workspace_ids}
    for row in projects:
        if row.get("workspace_id") in project_count:
            project_count[row["workspace_id"]] += 1
    for row in tasks:
        if row.get("workspace_id") in task_count:
            task_count[row["workspace_id"]] += 1

    queued = 0
    seen_users: set[str] = set()
    for workspace in workspaces:
        owner_id = workspace.get("owner_id")
        if not owner_id or owner_id in seen_users:
            continue
        if project_count.get(workspace["id"], 0) or task_count.get(workspace["id"], 0):
            continue
        seen_users.add(owner_id)
        result = create_notification(
            workspace_id=workspace["id"],
            recipient_id=owner_id,
            kind="activation_nudge",
            title=ACTIVATION_TITLE,
            message=ACTIVATION_MESSAGE,
            action_url="/projects",
            metadata={"workspace_id": workspace["id"]},
            dedupe_key=f"activation-nudge:{owner_id}",
            subject=ACTIVATION_TITLE,
            service=service,
        )
        if result.notification_id or result.delivery_id:
            queued += 1
    return queued
