from __future__ import annotations

from unittest.mock import Mock

from app.services.notifications import create_notification


def _query(data) -> Mock:
    query = Mock()
    for method in ("select", "eq", "maybe_single", "insert"):
        getattr(query, method).return_value = query
    query.execute.return_value = Mock(data=data)
    return query


def _failing_query() -> Mock:
    query = _query(None)
    query.execute.side_effect = RuntimeError("database unavailable")
    return query


def test_create_notification_queues_in_app_and_email_using_defaults() -> None:
    preferences = _query(None)
    notification = _query([{"id": "notification-1"}])
    delivery = _query([{"id": "delivery-1"}])
    service = Mock()
    service.table.side_effect = [preferences, notification, delivery]
    service.auth.admin.get_user_by_id.return_value = Mock(
        user=Mock(email="USER@EXAMPLE.COM")
    )

    result = create_notification(
        workspace_id="workspace-1",
        recipient_id="user-1",
        kind="task_assigned",
        title="Task assigned",
        message="Draft the launch email.",
        action_url="https://gravityos.tech/tasks",
        dedupe_key="task-assigned:task-1:user-1",
        service=service,
    )

    assert result.notification_id == "notification-1"
    assert result.delivery_id == "delivery-1"
    assert [call.args[0] for call in service.table.call_args_list] == [
        "notification_preferences",
        "notifications",
        "email_deliveries",
    ]
    notification_payload = notification.insert.call_args.args[0]
    assert notification_payload["dedupe_key"] == "task-assigned:task-1:user-1"
    assert notification_payload["action_url"] == "https://gravityos.tech/tasks"
    delivery_payload = delivery.insert.call_args.args[0]
    assert delivery_payload["recipient_email"] == "user@example.com"
    assert delivery_payload["notification_id"] == "notification-1"
    assert delivery_payload["idempotency_key"] == "task-assigned:task-1:user-1"


def test_relative_in_app_url_becomes_absolute_only_for_email() -> None:
    preferences = _query(None)
    notification = _query([{"id": "notification-1"}])
    delivery = _query([{"id": "delivery-1"}])
    service = Mock()
    service.table.side_effect = [preferences, notification, delivery]

    create_notification(
        workspace_id="workspace-1",
        recipient_id="user-1",
        recipient_email="user@example.com",
        kind="task_assigned",
        title="Task assigned",
        message="Draft the launch email.",
        action_url="/tasks?task=task-1",
        dedupe_key="task-assigned:task-1:user-1",
        service=service,
    )

    assert notification.insert.call_args.args[0]["action_url"] == "/tasks?task=task-1"
    assert delivery.insert.call_args.args[0]["template_data"]["action_url"].endswith(
        "/tasks?task=task-1"
    )


def test_event_preference_disables_both_channels() -> None:
    preferences = _query({"task_assignments": False})
    service = Mock()
    service.table.return_value = preferences

    result = create_notification(
        workspace_id="workspace-1",
        recipient_id="user-1",
        kind="task_assigned",
        title="Task assigned",
        message="Draft the launch email.",
        service=service,
    )

    assert result.notification_id is None
    assert result.delivery_id is None
    assert service.table.call_count == 1
    service.auth.admin.get_user_by_id.assert_not_called()


def test_email_can_be_queued_when_in_app_is_disabled() -> None:
    preferences = _query({"in_app_enabled": False, "email_enabled": True, "mentions": True})
    delivery = _query([{"id": "delivery-1"}])
    service = Mock()
    service.table.side_effect = [preferences, delivery]

    result = create_notification(
        workspace_id="workspace-1",
        recipient_id="user-1",
        recipient_email="USER@example.com",
        kind="comment_mention",
        title="You were mentioned",
        message="Open the comment.",
        dedupe_key="mention:comment-1:user-1",
        service=service,
    )

    assert result.notification_id is None
    assert result.delivery_id == "delivery-1"
    assert [call.args[0] for call in service.table.call_args_list] == [
        "notification_preferences",
        "email_deliveries",
    ]


def test_notification_failures_are_best_effort() -> None:
    service = Mock()
    service.table.side_effect = RuntimeError("database unavailable")

    result = create_notification(
        workspace_id="workspace-1",
        recipient_id="user-1",
        kind="task_assigned",
        title="Task assigned",
        message="Draft the launch email.",
        service=service,
    )

    assert result.notification_id is None
    assert result.delivery_id is None


def test_outbox_failure_preserves_successful_in_app_result() -> None:
    preferences = _query(None)
    notification = _query([{"id": "notification-1"}])
    failed_delivery = _failing_query()
    missing_delivery = _query(None)
    service = Mock()
    service.table.side_effect = [preferences, notification, failed_delivery, missing_delivery]

    result = create_notification(
        workspace_id="workspace-1",
        recipient_id="user-1",
        recipient_email="user@example.com",
        kind="task_assigned",
        title="Task assigned",
        message="Draft the launch email.",
        dedupe_key="task-assigned:task-1:user-1",
        service=service,
    )

    assert result.notification_id == "notification-1"
    assert result.delivery_id is None


def test_existing_deduped_notification_can_recover_missing_email() -> None:
    preferences = _query(None)
    failed_notification = _failing_query()
    existing_notification = _query({"id": "notification-1"})
    delivery = _query([{"id": "delivery-1"}])
    service = Mock()
    service.table.side_effect = [
        preferences,
        failed_notification,
        existing_notification,
        delivery,
    ]

    result = create_notification(
        workspace_id="workspace-1",
        recipient_id="user-1",
        recipient_email="user@example.com",
        kind="task_deadline_reminder",
        title="Task due tomorrow",
        message="Finish it.",
        dedupe_key="deadline:task-1:user-1:1",
        service=service,
    )

    assert result.notification_id == "notification-1"
    assert result.delivery_id == "delivery-1"


def test_auth_email_lookup_failure_does_not_erase_in_app_result() -> None:
    preferences = _query(None)
    notification = _query([{"id": "notification-1"}])
    service = Mock()
    service.table.side_effect = [preferences, notification]
    service.auth.admin.get_user_by_id.side_effect = RuntimeError("auth unavailable")

    result = create_notification(
        workspace_id="workspace-1",
        recipient_id="user-1",
        kind="task_assigned",
        title="Task assigned",
        message="Draft the launch email.",
        service=service,
    )

    assert result.notification_id == "notification-1"
    assert result.delivery_id is None
