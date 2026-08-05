"""Notification preference API behavior."""

from __future__ import annotations

from unittest.mock import Mock

from app.core.auth import AuthContext
from app.routers.notifications import (
    NotificationPreferencesUpdate,
    get_notification_preferences,
    update_notification_preferences,
)


def _auth() -> AuthContext:
    return AuthContext(user_id="user-1", email="user@example.com", token="token")


def _query(data) -> Mock:
    query = Mock()
    for method in ("select", "eq", "maybe_single", "upsert"):
        getattr(query, method).return_value = query
    query.execute.return_value = Mock(data=data)
    return query


def test_preferences_return_enabled_defaults_before_first_save() -> None:
    query = _query(None)
    db = Mock()
    db.table.return_value = query

    result = get_notification_preferences(_auth(), db)

    assert result["user_id"] == "user-1"
    assert result["email_enabled"] is True
    assert result["deadline_reminders"] is True
    assert result["reminder_days_before"] == [3, 1, 0]


def test_preferences_are_upserted_only_for_authenticated_user() -> None:
    saved = {
        "user_id": "user-1",
        "email_enabled": False,
        "in_app_enabled": True,
        "task_assignments": True,
        "mentions": True,
        "approval_updates": True,
        "deadline_reminders": True,
        "reminder_days_before": [7, 1, 0],
    }
    query = _query([saved])
    db = Mock()
    db.table.return_value = query

    result = update_notification_preferences(
        NotificationPreferencesUpdate(
            email_enabled=False,
            reminder_days_before=[0, 7, 1, 7],
        ),
        _auth(),
        db,
    )

    assert result == saved
    payload = query.upsert.call_args.args[0]
    assert payload["user_id"] == "user-1"
    assert payload["reminder_days_before"] == [7, 1, 0]
    assert query.upsert.call_args.kwargs["on_conflict"] == "user_id"
