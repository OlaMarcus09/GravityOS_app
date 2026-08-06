from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import Mock, patch

from app.jobs.notifications import (
    _recover_stale_email_deliveries,
    deliver_pending_emails,
    generate_deadline_reminders,
    run_notification_cycle,
)
from app.services.notifications import NotificationResult


class Query:
    def __init__(self, service, table: str):
        self.service = service
        self.table = table
        self.operation = "select"
        self.payload = None
        self.filters = []

    def select(self, *_args, **_kwargs):
        return self

    def update(self, payload):
        self.operation = "update"
        self.payload = payload
        return self

    def eq(self, column, value):
        self.filters.append(lambda row: row.get(column) == value)
        return self

    def lte(self, column, value):
        self.filters.append(lambda row: column not in row or row.get(column) <= value)
        return self

    def in_(self, column, values):
        self.filters.append(lambda row: column not in row or row.get(column) in values)
        return self

    @property
    def not_(self):
        return self

    def __getattr__(self, _name):
        return lambda *_args, **_kwargs: self

    def execute(self):
        if self.operation == "update":
            self.service.updates.append((self.table, self.payload))
            return Mock(data=[{"id": "claimed"}])
        rows = self.service.rows.get(self.table, [])
        return Mock(data=[row for row in rows if all(predicate(row) for predicate in self.filters)])


class Service:
    def __init__(self, rows):
        self.rows = rows
        self.updates = []

    def table(self, name):
        return Query(self, name)


def test_generate_deadline_reminders_queues_user_local_three_day_notice() -> None:
    service = Service(
        {
            "notification_preferences": [
                {
                    "user_id": "user-1",
                    "deadline_reminders": True,
                    "reminder_days_before": [3, 1, 0],
                }
            ],
            "tasks": [
                {
                    "id": "task-1",
                    "workspace_id": "workspace-1",
                    "title": "Approve masters",
                    "due_date": "2026-08-08",
                    "assignee_id": "user-1",
                    "status": "todo",
                }
            ],
            "profiles": [{"id": "user-1", "timezone": "Africa/Lagos"}],
        }
    )
    with patch(
        "app.jobs.notifications.create_notification",
        return_value=NotificationResult(notification_id="notification-1"),
    ) as create:
        queued = generate_deadline_reminders(
            service=service, now=datetime(2026, 8, 5, 9, tzinfo=timezone.utc)
        )

    assert queued == 1
    kwargs = create.call_args.kwargs
    assert kwargs["kind"] == "task_deadline_reminder"
    assert kwargs["action_url"] == "/tasks?task=task-1"
    assert kwargs["metadata"]["days_before"] == 3
    assert kwargs["dedupe_key"] == "task-deadline:task-1:user-1:2026-08-08:3"


def test_generate_deadline_reminders_uses_defaults_without_preference_row() -> None:
    service = Service(
        {
            "notification_preferences": [],
            "tasks": [
                {
                    "id": "task-1",
                    "workspace_id": "workspace-1",
                    "title": "Approve masters",
                    "due_date": "2026-08-06",
                    "assignee_id": "user-1",
                    "status": "todo",
                }
            ],
            "profiles": [{"id": "user-1", "timezone": None}],
        }
    )
    with patch(
        "app.jobs.notifications.create_notification",
        return_value=NotificationResult(delivery_id="delivery-1"),
    ) as create:
        queued = generate_deadline_reminders(
            service=service, now=datetime(2026, 8, 5, 9, tzinfo=timezone.utc)
        )

    assert queued == 1
    assert create.call_args.kwargs["metadata"]["days_before"] == 1


def _delivery(attempts=0, max_attempts=5):
    return {
        "id": "delivery-1",
        "notification_id": "notification-1",
        "recipient_email": "user@example.com",
        "subject": "Task due soon",
        "template_data": {"title": "Task due soon", "message": "Finish it."},
        "idempotency_key": "deadline:task-1:user-1",
        "attempts": attempts,
        "max_attempts": max_attempts,
        "status": "pending",
        "next_attempt_at": "2026-08-05T08:00:00+00:00",
        "updated_at": "2026-08-05T08:00:00+00:00",
    }


def test_deliver_pending_emails_marks_delivery_and_notification_sent() -> None:
    service = Service({"email_deliveries": [_delivery()]})
    resend = Mock()
    resend.send_email.return_value = "resend-message-1"

    result = deliver_pending_emails(
        service=service,
        resend=resend,
        now=datetime(2026, 8, 5, 9, tzinfo=timezone.utc),
    )

    assert result == {"sent": 1, "failed": 0}
    assert resend.send_email.call_args.kwargs["idempotency_key"] == "deadline:task-1:user-1"
    states = [payload["status"] for table, payload in service.updates if table == "email_deliveries"]
    assert states == ["processing", "sent"]
    assert any(table == "notifications" and "emailed_at" in payload for table, payload in service.updates)


def test_delivery_failure_schedules_retry_then_cancels_when_exhausted() -> None:
    resend = Mock()
    resend.send_email.side_effect = RuntimeError("provider unavailable")

    retry_service = Service({"email_deliveries": [_delivery(attempts=0, max_attempts=5)]})
    retry_result = deliver_pending_emails(service=retry_service, resend=resend)
    assert retry_result == {"sent": 0, "failed": 1}
    assert retry_service.updates[-1][1]["status"] == "failed"
    assert retry_service.updates[-1][1]["next_attempt_at"]

    final_service = Service({"email_deliveries": [_delivery(attempts=4, max_attempts=5)]})
    final_result = deliver_pending_emails(service=final_service, resend=resend)
    assert final_result == {"sent": 0, "failed": 1}
    assert final_service.updates[-1][1]["status"] == "cancelled"


def test_stale_processing_delivery_is_released_for_immediate_retry() -> None:
    service = Service(
        {
            "email_deliveries": [
                {
                    **_delivery(attempts=1),
                    "status": "processing",
                    "updated_at": "2026-08-05T08:00:00+00:00",
                }
            ]
        }
    )
    now = datetime(2026, 8, 5, 9, tzinfo=timezone.utc)

    recovered = _recover_stale_email_deliveries(service=service, now=now)

    assert recovered == 1
    payload = service.updates[-1][1]
    assert payload["status"] == "failed"
    assert payload["next_attempt_at"] == now.isoformat()
    assert "lease expired" in payload["last_error"].lower()


def test_stale_processing_delivery_is_cancelled_when_attempts_are_exhausted() -> None:
    service = Service(
        {
            "email_deliveries": [
                {
                    **_delivery(attempts=5, max_attempts=5),
                    "status": "processing",
                    "updated_at": "2026-08-05T08:00:00+00:00",
                }
            ]
        }
    )

    recovered = _recover_stale_email_deliveries(
        service=service,
        now=datetime(2026, 8, 5, 9, tzinfo=timezone.utc),
    )

    assert recovered == 1
    payload = service.updates[-1][1]
    assert payload["status"] == "cancelled"
    assert "next_attempt_at" not in payload


def test_cron_cycle_generates_reminders_then_drains_outbox() -> None:
    service = Mock()
    resend = Mock()
    resend_context = Mock()
    resend_context.__enter__ = Mock(return_value=resend)
    resend_context.__exit__ = Mock(return_value=None)

    with (
        patch("app.jobs.notifications.get_service_client", return_value=service),
        patch("app.jobs.notifications.ResendClient", return_value=resend_context),
        patch("app.jobs.notifications.generate_deadline_reminders", return_value=2) as generate,
        patch(
            "app.jobs.notifications.deliver_pending_emails",
            return_value={"sent": 3, "failed": 1},
        ) as deliver,
    ):
        result = run_notification_cycle()

    assert result == {"queued": 2, "sent": 3, "failed": 1}
    generate.assert_called_once_with(service=service)
    deliver.assert_called_once_with(service=service, resend=resend)
