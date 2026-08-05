"""Small Resend HTTP client and safe notification email rendering."""

from __future__ import annotations

from dataclasses import dataclass
from html import escape
from typing import Any

import httpx

from app.core.config import get_settings

RESEND_BASE_URL = "https://api.resend.com"


class ResendNotConfiguredError(RuntimeError):
    """Raised when application email is attempted without a Resend API key."""


@dataclass(frozen=True)
class RenderedEmail:
    subject: str
    html: str
    text: str


def render_notification_email(
    *,
    subject: str,
    title: str,
    message: str,
    action_url: str | None = None,
    action_label: str = "Open Gravity OS",
) -> RenderedEmail:
    """Render a deliberately small template, escaping every dynamic value."""
    safe_subject = subject.strip()
    safe_title = escape(title.strip())
    safe_message = escape(message.strip()).replace("\n", "<br>")
    safe_url = escape(action_url, quote=True) if action_url else None
    safe_label = escape(action_label.strip())
    button = ""
    text_action = ""
    if safe_url:
        button = (
            '<p style="margin:28px 0">'
            f'<a href="{safe_url}" style="background:#18181b;color:#fff;'
            'padding:12px 18px;border-radius:8px;text-decoration:none;'
            f'font-weight:600">{safe_label}</a></p>'
        )
        text_action = f"\n\n{action_label.strip()}: {action_url}"

    html = (
        '<!doctype html><html><body style="margin:0;background:#f4f4f5;'
        'font-family:Arial,sans-serif;color:#18181b">'
        '<div style="max-width:600px;margin:0 auto;padding:32px 16px">'
        '<div style="background:#fff;border:1px solid #e4e4e7;border-radius:12px;'
        'padding:28px">'
        '<p style="margin:0 0 24px;font-size:18px;font-weight:700">Gravity OS</p>'
        f'<h1 style="margin:0 0 12px;font-size:24px">{safe_title}</h1>'
        f'<p style="margin:0;line-height:1.6;color:#52525b">{safe_message}</p>'
        f"{button}"
        '<p style="margin:28px 0 0;font-size:12px;color:#71717a">'
        "You received this because notifications are enabled for your Gravity OS account."
        "</p></div></div></body></html>"
    )
    text = (
        f"Gravity OS\n\n{title.strip()}\n\n{message.strip()}"
        f"{text_action}\n\nManage notification preferences in Gravity OS."
    )
    return RenderedEmail(subject=safe_subject, html=html, text=text)


class ResendClient:
    """Synchronous Resend client suitable for a background delivery worker."""

    def __init__(
        self,
        *,
        api_key: str | None = None,
        email_from: str | None = None,
        reply_to: str | None = None,
        http_client: httpx.Client | None = None,
    ) -> None:
        settings = get_settings()
        self.api_key = api_key if api_key is not None else getattr(settings, "resend_api_key", "")
        self.email_from = (
            email_from if email_from is not None else getattr(settings, "email_from", "")
        )
        self.reply_to = (
            reply_to if reply_to is not None else getattr(settings, "email_reply_to", "")
        )
        self._owns_http = http_client is None
        self.http = http_client or httpx.Client(base_url=RESEND_BASE_URL, timeout=20.0)

    def send_email(
        self,
        *,
        recipient: str,
        email: RenderedEmail,
        idempotency_key: str,
    ) -> str:
        if not self.api_key or not self.email_from:
            raise ResendNotConfiguredError("RESEND_API_KEY and EMAIL_FROM must be configured")
        payload: dict[str, Any] = {
            "from": self.email_from,
            "to": [recipient.strip().lower()],
            "subject": email.subject,
            "html": email.html,
            "text": email.text,
        }
        if self.reply_to:
            payload["reply_to"] = self.reply_to
        response = self.http.post(
            "/emails",
            json=payload,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Idempotency-Key": idempotency_key,
            },
        )
        response.raise_for_status()
        message_id = response.json().get("id")
        if not message_id:
            raise RuntimeError("Resend response did not include a message id")
        return str(message_id)

    def close(self) -> None:
        if self._owns_http:
            self.http.close()

    def __enter__(self) -> ResendClient:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()
