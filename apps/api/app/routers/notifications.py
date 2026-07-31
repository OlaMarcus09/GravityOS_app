"""Persistent in-app notification routes."""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from supabase import Client

from app.core.auth import AuthContext, get_auth_context
from app.core.deps import get_db

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("")
def list_notifications(
    unread_only: bool = Query(False),
    limit: int = Query(30, ge=1, le=100),
    auth: AuthContext = Depends(get_auth_context),
    db: Client = Depends(get_db),
) -> dict:
    query = db.table("notifications").select("*")
    if unread_only:
        query = query.is_("read_at", "null")
    rows = query.order("created_at", desc=True).limit(limit).execute().data or []
    unread = db.table("notifications").select("id", count="exact").is_("read_at", "null").execute().count or 0
    return {"items": rows, "unread_count": unread}


@router.patch("/{notification_id}/read")
def mark_notification_read(
    notification_id: str,
    auth: AuthContext = Depends(get_auth_context),
    db: Client = Depends(get_db),
) -> dict:
    result = db.table("notifications").update({
        "read_at": datetime.now(timezone.utc).isoformat(),
    }).eq("id", notification_id).execute()
    if not result.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail={"error": {"code": "not_found", "message": "notification not found"}})
    return result.data[0]


@router.post("/read-all", status_code=status.HTTP_204_NO_CONTENT)
def mark_all_notifications_read(
    auth: AuthContext = Depends(get_auth_context),
    db: Client = Depends(get_db),
) -> None:
    db.table("notifications").update({
        "read_at": datetime.now(timezone.utc).isoformat(),
    }).is_("read_at", "null").execute()


@router.delete("/{notification_id}", status_code=status.HTTP_204_NO_CONTENT)
def dismiss_notification(
    notification_id: str,
    auth: AuthContext = Depends(get_auth_context),
    db: Client = Depends(get_db),
) -> None:
    db.table("notifications").delete().eq("id", notification_id).execute()
