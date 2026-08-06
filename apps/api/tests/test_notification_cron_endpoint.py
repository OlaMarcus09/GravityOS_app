from __future__ import annotations

from unittest.mock import Mock, patch

from fastapi.testclient import TestClient

from app.main import create_app


def _client(secret: str) -> TestClient:
    settings = Mock(
        cors_origin_list=[],
        environment="test",
        notification_cron_secret=secret,
    )
    with patch("app.main.get_settings", return_value=settings):
        return TestClient(create_app())


def test_notification_cron_rejects_missing_server_configuration() -> None:
    response = _client("").post(
        "/internal/notifications/run",
        headers={"X-Cron-Key": "anything"},
    )

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "cron_not_configured"


def test_notification_cron_rejects_invalid_key() -> None:
    response = _client("correct-secret").post(
        "/internal/notifications/run",
        headers={"X-Cron-Key": "wrong-secret"},
    )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "invalid_cron_key"


def test_notification_cron_runs_cycle_with_valid_key() -> None:
    with patch(
        "app.main.run_notification_cycle",
        return_value={"queued": 2, "sent": 3, "failed": 0},
    ) as run:
        response = _client("correct-secret").post(
            "/internal/notifications/run",
            headers={"X-Cron-Key": "correct-secret"},
        )

    assert response.status_code == 200
    assert response.json() == {"queued": 2, "sent": 3, "failed": 0}
    run.assert_called_once_with()
