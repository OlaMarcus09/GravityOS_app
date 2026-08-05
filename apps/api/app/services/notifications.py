"""Central best-effort creation of in-app and queued email notifications."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import uuid4

from app.core.config import get_settings
from app.core.db import get_service_client

PREFERENCE_BY_KIND = {
    "task_assigned": "task_assignments",
    "comment_mention": "mentions",
    "task_approval_requested": "approval_updates",
    "task_approved": "approval_updates",
    "task_rejected": "approval_updates",
    "task_deadline_reminder": "deadline_reminders",
}


@dataclass(frozen=True)
class NotificationResult:
    notification_id: str | None = None
    delivery_id: str | None = None


def _single_data(response: Any) -> dict[str, Any] | None:
    data = getattr(response, "data", None)
    if isinstance(data, list):
        return data[0] if data else None
    return data


def _preferences(service: Any, recipient_id: str | None) -> dict[str, Any]:
    if not recipient_id:
        return {}
    try:
        response = (
            service.table("notification_preferences")
            .select("*")
            .eq("user_id", recipient_id)
            .maybe_single()
            .execute()
        )
        return _single_data(response) or {}
    except Exception:
        return {}


def _recipient_email(service: Any, recipient_id: str | None, email: str | None) -> str | None:
    if email:
        return email.strip().lower()
    if not recipient_id:
        return None
    response = service.auth.admin.get_user_by_id(recipient_id)
    user = getattr(response, "user", response)
    resolved = getattr(user, "email", None)
    return resolved.strip().lower() if resolved else None


def _email_action_url(action_url: str | None) -> str | None:
    if not action_url or not action_url.startswith("/"):
        return action_url
    return f"{get_settings().web_app_url.rstrip('/')}{action_url}"


def create_notification(
    *,
    workspace_id: str | None,
    recipient_id: str | None,
    kind: str,
    title: str,
    message: str,
    recipient_email: str | None = None,
    action_url: str | None = None,
    metadata: dict[str, Any] | None = None,
    dedupe_key: str | None = None,
    subject: str | None = None,
    service: Any | None = None,
) -> NotificationResult:
    """Create enabled channels without allowing notification failure to break app work."""
    try:
        service = service or get_service_client()
    except Exception:
        return NotificationResult()
    preferences = _preferences(service, recipient_id)
    event_preference = PREFERENCE_BY_KIND.get(kind)
    event_enabled = preferences.get(event_preference, True) if event_preference else True
    in_app_enabled = preferences.get("in_app_enabled", True) and event_enabled
    email_enabled = preferences.get("email_enabled", True) and event_enabled
    notification_id = None

    if in_app_enabled:
        payload = {
            "workspace_id": workspace_id,
            "recipient_id": recipient_id,
            "recipient_email": recipient_email.strip().lower() if recipient_email else None,
            "kind": kind,
            "title": title,
            "message": message,
            "action_url": action_url,
            "metadata": metadata or {},
            "dedupe_key": dedupe_key,
        }
        try:
            inserted = service.table("notifications").insert(payload).execute()
            notification = _single_data(inserted)
            notification_id = notification.get("id") if notification else None
        except Exception:
            if dedupe_key:
                try:
                    existing = (
                        service.table("notifications")
                        .select("id")
                        .eq("dedupe_key", dedupe_key)
                        .maybe_single()
                        .execute()
                    )
                    notification = _single_data(existing)
                    notification_id = notification.get("id") if notification else None
                except Exception:
                    pass

    delivery_id = None
    resolved_email = None
    if email_enabled:
        try:
            resolved_email = _recipient_email(service, recipient_id, recipient_email)
        except Exception:
            pass
    if email_enabled and resolved_email:
        idempotency_key = dedupe_key or f"notification:{notification_id or uuid4()}"
        delivery_payload = {
            "notification_id": notification_id,
            "workspace_id": workspace_id,
            "recipient_id": recipient_id,
            "recipient_email": resolved_email,
            "template_key": "notification",
            "subject": subject or title,
            "template_data": {
                "title": title,
                "message": message,
                "action_url": _email_action_url(action_url),
                "action_label": "Open Gravity OS",
            },
            "idempotency_key": idempotency_key,
        }
        try:
            inserted = service.table("email_deliveries").insert(delivery_payload).execute()
            delivery = _single_data(inserted)
            delivery_id = delivery.get("id") if delivery else None
        except Exception:
            try:
                existing = (
                    service.table("email_deliveries")
                    .select("id")
                    .eq("idempotency_key", idempotency_key)
                    .maybe_single()
                    .execute()
                )
                delivery = _single_data(existing)
                delivery_id = delivery.get("id") if delivery else None
            except Exception:
                pass
    return NotificationResult(notification_id=notification_id, delivery_id=delivery_id)
