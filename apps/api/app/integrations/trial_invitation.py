"""Render a promotional trial invitation; delivery requires separate approval."""

from __future__ import annotations

from html import escape
from urllib.parse import urlparse

from app.integrations.resend import RenderedEmail

SUBJECT = "Your 7 Days of GravityOS Pro Are Waiting 🎁"
PLAN_BILLING_URL = "https://www.gravityos.tech/settings"


def _https_url(value: str, *, host: str | None = None) -> str:
    parsed = urlparse(value)
    if parsed.scheme != "https" or not parsed.netloc or parsed.username or parsed.password:
        raise ValueError("An absolute HTTPS URL is required")
    if host and parsed.hostname != host:
        raise ValueError("The Plan & Billing link must use the production site")
    return value


def render_trial_invitation(*, first_name: str | None, unsubscribe_url: str) -> RenderedEmail:
    """Return one personalized HTML/text email. No delivery or claim side effect."""
    _https_url(PLAN_BILLING_URL, host="www.gravityos.tech")
    _https_url(unsubscribe_url)
    parts = (first_name or "").strip().split(maxsplit=1)
    name = parts[0][:60] if parts else "there"
    safe_name = escape(name)
    cta = escape(PLAN_BILLING_URL, quote=True)
    opt_out = escape(unsubscribe_url, quote=True)
    html = f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="margin:0;background:#f6f5f1;color:#17211d;font-family:Arial,Helvetica,sans-serif">
<table role="presentation" cellpadding="0" cellspacing="0" width="100%" style="background:#f6f5f1"><tr><td align="center" style="padding:24px 12px">
<table role="presentation" cellpadding="0" cellspacing="0" width="100%" style="max-width:600px;background:#ffffff;border:1px solid #e3e9e2;border-radius:16px">
<tr><td style="padding:28px 28px 10px"><div style="font-size:20px;font-weight:800;letter-spacing:-.02em">GravityOS</div></td></tr>
<tr><td style="padding:12px 28px 28px"><p style="font-size:16px;line-height:1.6;margin:0 0 14px">Hi {safe_name},</p>
<h1 style="font-size:28px;line-height:1.2;margin:0 0 16px">Your seven days of Pro are waiting 🎁</h1>
<p style="font-size:16px;line-height:1.6;margin:0 0 14px">Thank you for being one of the early GravityOS users. We appreciate the trust you've placed in us while building your work here.</p>
<p style="font-size:16px;line-height:1.6;margin:0 0 14px">You're invited to enjoy seven days of GravityOS Pro, free. Explore more room for your projects, catalogue, and release planning with the workspace you already use.</p>
<p style="font-size:16px;line-height:1.6;margin:0 0 20px">Claim by <strong>November 15, 2026 at 11:59:59 PM WAT</strong>. Your full 168 hours begin only when you choose <strong>Claim My Trial</strong> in Plan &amp; Billing.</p>
<p style="margin:0 0 20px"><a href="{cta}" style="display:inline-block;background:#164b38;color:#ffffff;text-decoration:none;font-weight:700;padding:14px 22px;border-radius:8px">Open Plan &amp; Billing</a></p>
<p style="font-size:14px;line-height:1.6;margin:0">No payment card is required. There are no automatic charges. After your trial, your workspace returns to Free and your existing data remains available.</p>
</td></tr><tr><td style="padding:20px 28px 28px;border-top:1px solid #e3e9e2;font-size:12px;line-height:1.5;color:#52645a">This invitation was sent to an eligible GravityOS account owner. <a href="{opt_out}" style="color:#164b38">Unsubscribe from trial invitations</a>.</td></tr>
</table></td></tr></table></body></html>'''
    text = (f"Hi {name},\n\nYour seven days of GravityOS Pro are waiting 🎁\n\n"
            "Thank you for being one of the early GravityOS users. We appreciate the trust "
            "you've placed in us while building your work here.\n\n"
            "You're invited to enjoy seven days of GravityOS Pro, free, with your existing workspace. "
            "Claim by November 15, 2026 at 11:59:59 PM WAT. Your full 168 hours begin only when "
            "you choose Claim My Trial in Plan & Billing.\n\n"
            f"Open Plan & Billing: {PLAN_BILLING_URL}\n\n"
            "No payment card is required. There are no automatic charges. After your trial, "
            "your workspace returns to Free and your existing data remains available.\n\n"
            f"Unsubscribe from trial invitations: {unsubscribe_url}")
    return RenderedEmail(subject=SUBJECT, html=html, text=text)
