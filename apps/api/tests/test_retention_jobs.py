from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import Mock, patch

from app.jobs.activation import generate_activation_nudges
from app.jobs.digest import generate_weekly_digests
from app.jobs.dormant_checkin import generate_dormant_checkins
from app.services.notifications import NotificationResult


class Query:
    def __init__(self, service, table):
        self.service = service
        self.table_name = table

    def __getattr__(self, _name):
        return lambda *_args, **_kwargs: self

    def execute(self):
        return SimpleNamespace(data=self.service.rows.get(self.table_name, []))


class Service:
    def __init__(self, rows, users=None):
        self.rows = rows
        self.users = users or []
        self.inserts = []
        self.auth = SimpleNamespace(admin=SimpleNamespace(list_users=lambda: SimpleNamespace(users=self.users)))

    def table(self, name):
        query = Query(self, name)
        original_execute = query.execute
        def execute():
            if name == "retention_checkins":
                return SimpleNamespace(data=self.rows.get(name, []))
            return original_execute()
        query.execute = execute
        return query


def test_activation_nudge_targets_empty_workspace_with_concrete_action():
    service = Service({
        "workspaces": [{"id": "ws-1", "owner_id": "user-1", "created_at": "2026-08-09T10:00:00Z"}],
        "projects": [], "tasks": [],
    })
    with patch("app.jobs.activation.create_notification", return_value=NotificationResult(notification_id="n-1")) as create:
        queued = generate_activation_nudges(service=service, now=datetime(2026, 8, 10, 10, tzinfo=timezone.utc))
    assert queued == 1
    kwargs = create.call_args.kwargs
    assert kwargs["dedupe_key"] == "activation-nudge:user-1"
    assert kwargs["action_url"] == "/projects"
    assert "first project" in kwargs["message"].lower()


def test_weekly_digest_skips_user_with_nothing_to_report():
    service = Service({
        "notification_preferences": [{"user_id": "user-1", "weekly_digests": True, "in_app_enabled": True, "email_enabled": True}],
        "workspace_members": [{"workspace_id": "ws-1", "user_id": "user-1"}],
        "profiles": [{"id": "user-1", "timezone": "UTC"}],
        "tasks": [], "gravity_scores": [],
    })
    with patch("app.jobs.digest.create_notification") as create:
        queued = generate_weekly_digests(service=service, now=datetime(2026, 8, 10, 9, tzinfo=timezone.utc))
    assert queued == 0
    create.assert_not_called()


def test_weekly_digest_queues_non_empty_iso_week_summary():
    service = Service({
        "notification_preferences": [{"user_id": "user-1", "weekly_digests": True, "in_app_enabled": True, "email_enabled": True}],
        "workspace_members": [{"workspace_id": "ws-1", "user_id": "user-1"}],
        "profiles": [{"id": "user-1", "display_name": "Ada West", "timezone": "UTC"}],
        "workspaces": [{"id": "ws-1", "name": "Ada Live Team"}],
        "tasks": [{"workspace_id": "ws-1", "title": "Ship single", "assignee_id": "user-1", "status": "done", "completed_at": "2026-08-09T10:00:00Z"}],
        "gravity_scores": [],
    })
    with patch("app.jobs.digest.create_notification", return_value=NotificationResult(delivery_id="d-1")) as create:
        queued = generate_weekly_digests(service=service, now=datetime(2026, 8, 10, 9, tzinfo=timezone.utc))
    assert queued == 1
    kwargs = create.call_args.kwargs
    assert kwargs["dedupe_key"] == "weekly-digest:user-1:2026-W33"
    assert kwargs["title"] == "Ada, your weekly Gravity OS digest"
    assert "Ada Live Team" in kwargs["message"]
    assert "you completed 1 assigned task" in kwargs["message"]
    assert "the team completed 1 task" in kwargs["message"]


def test_weekly_digest_personalizes_teammates_without_losing_team_totals():
    service = Service({
        "notification_preferences": [
            {"user_id": "user-1", "weekly_digests": True, "in_app_enabled": True, "email_enabled": True},
            {"user_id": "user-2", "weekly_digests": True, "in_app_enabled": True, "email_enabled": True},
        ],
        "workspace_members": [
            {"workspace_id": "ws-1", "user_id": "user-1"},
            {"workspace_id": "ws-1", "user_id": "user-2"},
        ],
        "profiles": [
            {"id": "user-1", "display_name": "Ada West", "timezone": "UTC"},
            {"id": "user-2", "display_name": "Marcus Cole", "timezone": "UTC"},
        ],
        "workspaces": [{"id": "ws-1", "name": "Live Band"}],
        "tasks": [
            {"workspace_id": "ws-1", "title": "Approve set list", "assignee_id": "user-1", "completed_at": "2026-08-09T10:00:00Z"},
            {"workspace_id": "ws-1", "title": "Confirm rehearsal", "assignee_id": "user-2", "due_date": "2026-08-12"},
        ],
        "gravity_scores": [],
    })
    with patch("app.jobs.digest.create_notification", return_value=NotificationResult(delivery_id="d-1")) as create:
        queued = generate_weekly_digests(service=service, now=datetime(2026, 8, 10, 9, tzinfo=timezone.utc))

    assert queued == 2
    calls = {call.kwargs["recipient_id"]: call.kwargs for call in create.call_args_list}
    assert calls["user-1"]["title"].startswith("Ada,")
    assert "you completed 1 assigned task" in calls["user-1"]["message"]
    assert "you have 0 assigned tasks due" in calls["user-1"]["message"]
    assert calls["user-2"]["title"].startswith("Marcus,")
    assert "you completed 0 assigned tasks" in calls["user-2"]["message"]
    assert "you have 1 assigned task due" in calls["user-2"]["message"]
    assert "the team completed 1 task" in calls["user-1"]["message"]
    assert "the team completed 1 task" in calls["user-2"]["message"]
    assert "1 team task is due" in calls["user-1"]["message"]
    assert "1 team task is due" in calls["user-2"]["message"]


def test_weekly_digest_keeps_multiple_workspace_summaries_separate():
    service = Service({
        "notification_preferences": [{"user_id": "user-1", "weekly_digests": True, "in_app_enabled": True, "email_enabled": True}],
        "workspace_members": [
            {"workspace_id": "ws-1", "user_id": "user-1"},
            {"workspace_id": "ws-2", "user_id": "user-1"},
        ],
        "profiles": [{"id": "user-1", "display_name": "Ada West", "timezone": "UTC"}],
        "workspaces": [{"id": "ws-1", "name": "Artist Team"}, {"id": "ws-2", "name": "Agency Team"}],
        "tasks": [
            {"workspace_id": "ws-1", "title": "Master artwork", "assignee_id": "user-1", "completed_at": "2026-08-09T10:00:00Z"},
            {"workspace_id": "ws-2", "title": "Confirm press", "assignee_id": "user-1", "due_date": "2026-08-12"},
        ],
        "gravity_scores": [],
    })
    with patch("app.jobs.digest.create_notification", return_value=NotificationResult(delivery_id="d-1")) as create:
        assert generate_weekly_digests(service=service, now=datetime(2026, 8, 10, 9, tzinfo=timezone.utc)) == 1

    message = create.call_args.kwargs["message"]
    assert "Artist Team:" in message
    assert "Agency Team:" in message
    assert message.index("Artist Team:") < message.index("Agency Team:")
    assert create.call_args.kwargs["metadata"]["workspace_count"] == 2


def test_dormant_checkin_uses_last_activity_and_skips_existing_period():
    user = SimpleNamespace(id="user-1", last_sign_in_at="2026-07-20T10:00:00Z")
    base_rows = {
        "workspace_members": [{"workspace_id": "ws-1", "user_id": "user-1"}],
        "workspace_activity_events": [{"actor_id": "user-1", "summary": "Finished the single rollout", "created_at": "2026-07-21T10:00:00Z"}],
        "retention_checkins": [],
    }
    service = Service(base_rows, [user])
    with patch("app.jobs.dormant_checkin.create_notification", return_value=NotificationResult(notification_id="n-1")) as create:
        queued = generate_dormant_checkins(service=service, now=datetime(2026, 8, 10, 10, tzinfo=timezone.utc))
    assert queued == 1
    assert "Finished the single rollout" in create.call_args.kwargs["message"]

    service.rows["retention_checkins"] = [{"dedupe_key": create.call_args.kwargs["dedupe_key"]}]
    with patch("app.jobs.dormant_checkin.create_notification") as duplicate:
        assert generate_dormant_checkins(service=service, now=datetime(2026, 8, 10, 10, tzinfo=timezone.utc)) == 0
    duplicate.assert_not_called()
