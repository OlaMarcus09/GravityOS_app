"""Project/task comments, mentions, and workspace activity."""

from __future__ import annotations

import re
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.core.db import get_service_client
from app.core.deps import WorkspaceContext, get_workspace_context, require_writer
from app.core.rate_limit import check_rate_limit
from app.schemas.collaboration import ActivityEventType, CommentCreate
from app.services.notifications import create_notification

router = APIRouter(prefix="/collaboration", tags=["collaboration"])

MENTION_PATTERN = re.compile(r"@\[(?P<display>[^\]\r\n]{1,100})\]\((?P<user_id>[0-9a-fA-F-]{36})\)")
TARGET_TABLES = {"project": "projects", "task": "tasks"}


def _attach_profiles(rows: list[dict], foreign_key: str, output_key: str) -> list[dict]:
    """Hydrate only collaboration-safe profile fields via the service client."""
    ids = {row.get(foreign_key) for row in rows if row.get(foreign_key)}
    profiles: dict[str, dict] = {}
    if ids:
        data = (
            get_service_client()
            .table("profiles")
            .select("id,display_name,avatar_url")
            .in_("id", list(ids))
            .execute()
            .data
            or []
        )
        profiles = {profile["id"]: profile for profile in data}
    for row in rows:
        row[output_key] = profiles.get(row.get(foreign_key))
    return rows


def _target_or_404(ctx: WorkspaceContext, target_type: str, target_id: str) -> dict:
    row = (
        ctx.db.table(TARGET_TABLES[target_type])
        .select("id,title")
        .eq("id", target_id)
        .eq("workspace_id", ctx.workspace_id)
        .maybe_single()
        .execute()
    )
    if not row.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "not_found", "message": f"{target_type} not found"}},
        )
    return row.data


def _activity(
    *,
    ctx: WorkspaceContext,
    event_type: str,
    target_type: str,
    target_id: str,
    summary: str,
    metadata: dict | None = None,
) -> None:
    try:
        get_service_client().table("workspace_activity_events").insert(
            {
                "workspace_id": ctx.workspace_id,
                "actor_id": ctx.auth.user_id,
                "event_type": event_type,
                "target_type": target_type,
                "target_id": target_id,
                "summary": summary,
                "metadata": metadata or {},
            }
        ).execute()
    except Exception:
        # Audit delivery should not turn a successful comment action into a 500.
        return


def _notify_mentions(ctx: WorkspaceContext, body: str, comment: dict, target: dict) -> None:
    mentioned_ids: set[str] = set()
    for match in MENTION_PATTERN.finditer(body):
        try:
            mentioned_ids.add(str(UUID(match.group("user_id"))))
        except ValueError:
            continue
    mentioned_ids.discard(ctx.auth.user_id.lower())
    if not mentioned_ids:
        return

    try:
        service = get_service_client()
        members = (
            service.table("workspace_members")
            .select("user_id")
            .eq("workspace_id", ctx.workspace_id)
            .in_("user_id", list(mentioned_ids))
            .execute()
            .data
            or []
        )
        action_url = (
            f"/{'projects' if comment['target_type'] == 'project' else 'tasks'}"
            f"?comments={comment['target_id']}"
        )
        for member in members:
            recipient_id = member["user_id"]
            create_notification(
                workspace_id=ctx.workspace_id,
                recipient_id=recipient_id,
                kind="comment_mention",
                title="You were mentioned in a comment",
                message=f"You were mentioned on {target['title']}.",
                action_url=action_url,
                metadata={
                    "comment_id": comment["id"],
                    "target_type": comment["target_type"],
                    "target_id": comment["target_id"],
                    "mentioned_by": ctx.auth.user_id,
                },
                dedupe_key=f"comment-mention:{comment['id']}:{recipient_id}",
                service=service,
            )
    except Exception:
        # Mentions are best-effort and must not fail the saved comment.
        return


@router.get("/comments")
def list_comments(
    target_type: Literal["project", "task"] = Query(...),
    target_id: UUID = Query(...),
    ctx: WorkspaceContext = Depends(get_workspace_context),
) -> list[dict]:
    _target_or_404(ctx, target_type, str(target_id))
    rows = (
        ctx.db.table("comments")
        .select("*")
        .eq("workspace_id", ctx.workspace_id)
        .eq("target_type", target_type)
        .eq("target_id", str(target_id))
        .order("created_at")
        .execute()
        .data
        or []
    )
    return _attach_profiles(rows, "author_id", "author")


@router.post("/comments", status_code=status.HTTP_201_CREATED)
def create_comment(
    body: CommentCreate,
    ctx: WorkspaceContext = Depends(require_writer),
) -> dict:
    check_rate_limit(f"comment:{ctx.workspace_id}:{ctx.auth.user_id}", limit=60)
    target = _target_or_404(ctx, body.target_type, str(body.target_id))
    result = (
        ctx.db.table("comments")
        .insert(
            {
                "workspace_id": ctx.workspace_id,
                "target_type": body.target_type,
                "target_id": str(body.target_id),
                "author_id": ctx.auth.user_id,
                "body": body.body,
            }
        )
        .execute()
    )
    comment = result.data[0]
    comment["author"] = {
        "id": ctx.auth.user_id,
        "display_name": None,
        "avatar_url": None,
    }
    profile = (
        ctx.db.table("profiles")
        .select("id,display_name,avatar_url")
        .eq("id", ctx.auth.user_id)
        .maybe_single()
        .execute()
    )
    if profile.data:
        comment["author"] = profile.data

    _activity(
        ctx=ctx,
        event_type="comment.created",
        target_type=body.target_type,
        target_id=str(body.target_id),
        summary=f"Commented on {target['title']}",
        metadata={"comment_id": comment["id"]},
    )
    _notify_mentions(ctx, body.body, comment, target)
    return comment


@router.delete("/comments/{comment_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_comment(
    comment_id: UUID,
    ctx: WorkspaceContext = Depends(require_writer),
) -> None:
    existing = (
        ctx.db.table("comments")
        .select("id,author_id,target_type,target_id")
        .eq("id", str(comment_id))
        .eq("workspace_id", ctx.workspace_id)
        .maybe_single()
        .execute()
    )
    if not existing.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "not_found", "message": "comment not found"}},
        )
    if existing.data["author_id"] != ctx.auth.user_id and ctx.role not in ("owner", "admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": {
                    "code": "forbidden",
                    "message": "only the author or an admin can delete this comment",
                }
            },
        )
    ctx.db.table("comments").delete().eq("id", str(comment_id)).eq(
        "workspace_id", ctx.workspace_id
    ).execute()
    _activity(
        ctx=ctx,
        event_type="comment.deleted",
        target_type=existing.data["target_type"],
        target_id=existing.data["target_id"],
        summary="Deleted a comment",
        metadata={"comment_id": str(comment_id)},
    )


@router.get("/activity")
def list_activity(
    limit: int = Query(50, ge=1, le=100),
    before: str | None = Query(None),
    project_id: UUID | None = Query(None),
    member_id: UUID | None = Query(None),
    event_type: ActivityEventType | None = Query(None),
    ctx: WorkspaceContext = Depends(get_workspace_context),
) -> list[dict]:
    query = (
        ctx.db.table("workspace_activity_events").select("*").eq("workspace_id", ctx.workspace_id)
    )
    if before:
        query = query.lt("created_at", before)
    if project_id:
        project_id_string = str(project_id)
        task_rows = (
            ctx.db.table("tasks")
            .select("id")
            .eq("workspace_id", ctx.workspace_id)
            .eq("project_id", project_id_string)
            .execute()
            .data
            or []
        )
        project_conditions = [
            f"and(target_type.eq.project,target_id.eq.{project_id_string})",
            f"metadata->>project_id.eq.{project_id_string}",
        ]
        task_ids = [row["id"] for row in task_rows]
        if task_ids:
            project_conditions.append(
                f"and(target_type.eq.task,target_id.in.({','.join(task_ids)}))"
            )
        query = query.or_(",".join(project_conditions))
    if member_id:
        query = query.eq("actor_id", str(member_id))
    if event_type:
        query = query.eq("event_type", event_type)
    rows = query.order("created_at", desc=True).limit(limit).execute().data or []
    return _attach_profiles(rows, "actor_id", "actor")
