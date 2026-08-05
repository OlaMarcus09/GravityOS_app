from __future__ import annotations

import httpx
import pytest

from app.integrations.resend import (
    ResendClient,
    ResendNotConfiguredError,
    render_notification_email,
)


def test_notification_template_escapes_dynamic_html() -> None:
    email = render_notification_email(
        subject="Task assigned",
        title='<script>alert("title")</script>',
        message="Review <strong>this</strong>",
        action_url='https://gravityos.tech/tasks?q="><script>',
    )

    assert "<script>" not in email.html
    assert "&lt;script&gt;" in email.html
    assert "&lt;strong&gt;this&lt;/strong&gt;" in email.html
    assert "Gravity OS" in email.text


def test_resend_client_sends_auth_and_idempotency_headers() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/emails"
        assert request.headers["authorization"] == "Bearer secret"
        assert request.headers["idempotency-key"] == "task:1:user:1"
        payload = request.read().decode()
        assert "notifications@gravityos.tech" in payload
        assert "user@example.com" in payload
        return httpx.Response(200, json={"id": "email-1"})

    http = httpx.Client(base_url="https://api.resend.com", transport=httpx.MockTransport(handler))
    client = ResendClient(
        api_key="secret",
        email_from="Gravity OS <notifications@gravityos.tech>",
        reply_to="support@gravityos.tech",
        http_client=http,
    )
    rendered = render_notification_email(subject="Task assigned", title="Task", message="Do it")

    assert client.send_email(
        recipient="USER@example.com", email=rendered, idempotency_key="task:1:user:1"
    ) == "email-1"
    http.close()


def test_resend_client_requires_key_and_sender() -> None:
    http = httpx.Client(
        base_url="https://api.resend.com",
        transport=httpx.MockTransport(lambda _: httpx.Response(200, json={"id": "email-1"})),
    )
    client = ResendClient(api_key="", email_from="", http_client=http)
    rendered = render_notification_email(subject="Hello", title="Hello", message="World")

    with pytest.raises(ResendNotConfiguredError):
        client.send_email(recipient="user@example.com", email=rendered, idempotency_key="one")
    http.close()
