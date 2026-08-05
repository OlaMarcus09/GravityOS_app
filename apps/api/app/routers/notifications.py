"""Persistent in-app notification routes."""
from __future__ import annotations

from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field, field_validator
from supabase import Client

from app.core.auth import AuthContext, get_auth_context
from app.core.deps import get_db

router = APIRouter(prefix="/notifications", tags=["notifications"])

DEFAULT_REMINDER_DAYS = [3, 1, 0]


class NotificationPreferencesUpdate(BaseModel):
    email_enabled: bool = True
    in_app_enabled: bool = True
    task_assignments: bool = True
    mentions: bool = True
    approval_updates: bool = True
    deadline_reminders: bool = True
    reminder_days_before: list[int] = Field(
        default_factory=lambda: DEFAULT_REMINDER_DAYS.copy(), min_length=1, max_length=10
    )

    @field_validator("reminder_days_before")
    @classmethod
    def validate_reminder_days(cls, value: list[int]) -> list[int]:
        if any(day < 0 or day > 365 for day in value):
            raise ValueError("reminder days must be between 0 and 365")
        return sorted(set(value), reverse=True)


def _default_preferences(user_id: str) -> dict:
    return {
        "user_id": user_id,
        **NotificationPreferencesUpdate().model_dump(),
    }


@router.get("/preferences")
def get_notification_preferences(
    auth: AuthContext = Depends(get_auth_context),
    db: Client = Depends(get_db),
) -> dict:
    result = (
        db.table("notification_preferences")
        .select("*")
        .eq("user_id", auth.user_id)
        .maybe_single()
        .execute()
    )
    return result.data if result and result.data else _default_preferences(auth.user_id)


@router.put("/preferences")
def update_notification_preferences(
    body: NotificationPreferencesUpdate,
    auth: AuthContext = Depends(get_auth_context),
    db: Client = Depends(get_db),
) -> dict:
    result = (
        db.table("notification_preferences")
        .upsert({"user_id": auth.user_id, **body.model_dump()}, on_conflict="user_id")
        .execute()
    )
    return result.data[0] if result.data else {"user_id": auth.user_id, **body.model_dump()}


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
