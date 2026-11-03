"""Single-purpose, opaque promotional opt-out links."""

from __future__ import annotations

from hashlib import sha256
import hmac
from uuid import UUID

from app.core.config import get_settings


class InvitationSigningUnavailable(RuntimeError):
    pass


def _key() -> bytes:
    value = get_settings().trial_invitation_signing_key.encode("utf-8")
    if len(value) < 32:
        raise InvitationSigningUnavailable("Trial invitation signing key is not configured")
    return value


def make_opt_out_token(delivery_id: UUID) -> str:
    identity = delivery_id.hex
    signature = hmac.new(_key(), f"trial-invite-opt-out:v1:{identity}".encode(), sha256).hexdigest()
    return f"{identity}.{signature}"


def verify_opt_out_token(token: str) -> UUID | None:
    parts = token.split(".")
    if len(parts) != 2 or len(parts[0]) != 32 or len(parts[1]) != 64:
        return None
    try:
        delivery_id = UUID(hex=parts[0])
        bytes.fromhex(parts[1])
    except ValueError:
        return None
    expected = make_opt_out_token(delivery_id).split(".", 1)[1]
    return delivery_id if hmac.compare_digest(parts[1], expected) else None


def make_opt_out_url(delivery_id: UUID) -> str:
    # The fragment is not sent in HTTP requests or ordinary access logs.
    return "https://www.gravityos.tech/trial-invitations/unsubscribe#token=" + make_opt_out_token(
        delivery_id
    )
