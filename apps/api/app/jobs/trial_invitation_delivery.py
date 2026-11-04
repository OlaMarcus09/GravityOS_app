"""Operator-only, one-at-a-time invitation delivery with durable no-retry semantics."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from typing import Any
from uuid import UUID

from app.core.config import get_settings
from app.integrations.resend import ResendClient
from app.integrations.trial_invitation import render_trial_invitation
from app.integrations.trial_invitation_provider import (
    InvitationProviderNotReady,
    TrialInvitationProvider,
)
from app.integrations.trial_invitation_tokens import make_opt_out_url

CAMPAIGN = "existing_user_trial_2026"


@dataclass(frozen=True)
class InvitationTarget:
    email: str
    first_name: str | None = None
    owner_id: UUID | None = None
    workspace_id: UUID | None = None
    kind: str = "test"

    @property
    def digest(self) -> bytes:
        return sha256(self.email.strip().lower().encode("utf-8")).digest()


class InvitationNotSendable(RuntimeError):
    pass


def _validate_target(target: InvitationTarget) -> None:
    if target.kind not in {"test", "initial", "reminder"}:
        raise InvitationNotSendable("Invalid invitation kind")
    if target.kind == "test":
        if target.email.strip().lower() != "highmarcus.eth@gmail.com":
            raise InvitationNotSendable("Test recipient is not authorized")
        if target.owner_id is not None or target.workspace_id is not None:
            raise InvitationNotSendable("Test delivery cannot change a customer account")
    elif target.owner_id is None or target.workspace_id is None:
        raise InvitationNotSendable("Customer delivery requires an owner and workspace")


def _current_eligibility(conn: Any, target: InvitationTarget) -> bool:
    window = conn.execute(
        """select enabled and starts_at is not null
                     and clock_timestamp() >= starts_at
                     and clock_timestamp() < ends_at + interval '1 second'
             from private.existing_user_trial_campaign where singleton"""
    ).fetchone()
    if not window or not window[0]:
        return False
    if target.kind == "test":
        return True
    if target.kind == "reminder" and not conn.execute(
        """select 1 from private.trial_invitation_deliveries
            where campaign = %s and kind = 'initial' and owner_id = %s
              and state in ('accepted', 'delivered')""",
        (CAMPAIGN, target.owner_id),
    ).fetchone():
        return False
    row = conn.execute(
        """select u.email_confirmed_at is not null, lower(btrim(u.email)),
                  private.existing_user_trial_status(u.id, %s, clock_timestamp()),
                  coalesce(p.email_enabled, true)
             from auth.users u
             left join public.notification_preferences p on p.user_id = u.id
            where u.id = %s""",
        (target.workspace_id, target.owner_id),
    ).fetchone()
    return bool(row and row[0] and row[1] == target.email.strip().lower()
                and row[2] == "eligible" and row[3])


def prepare_invitation(conn: Any, target: InvitationTarget) -> tuple[UUID, UUID] | None:
    """Reserve one unique owner/address/kind. Existing reservations never resend."""
    _validate_target(target)
    with conn.transaction():
        conn.execute(
            "select pg_advisory_xact_lock(hashtextextended(%s, 0))",
            (target.digest.hex(),),
        )
        if not _current_eligibility(conn, target):
            raise InvitationNotSendable("Recipient is no longer eligible")
        if conn.execute(
            """select 1 from private.trial_invitation_deliveries
                where campaign = %s and email_digest = %s and state <> 'prepared'""",
            (CAMPAIGN, target.digest),
        ).fetchone():
            return None
        row = conn.execute(
            """insert into private.trial_invitation_deliveries
                 (campaign, kind, owner_id, workspace_id, email_digest, eligibility_verified_at)
               values (%s, %s, %s, %s, %s, clock_timestamp())
               on conflict do nothing returning id, idempotency_key""",
            (CAMPAIGN, target.kind, target.owner_id, target.workspace_id, target.digest),
        ).fetchone()
        return (row[0], row[1]) if row else None


def deliver_prepared(
    conn: Any,
    target: InvitationTarget,
    delivery_id: UUID,
    *,
    provider: TrialInvitationProvider,
    sender: ResendClient,
) -> str:
    """Send once. An uncertain result is never automatically retried."""
    _validate_target(target)
    if not get_settings().trial_invitation_sending_enabled:
        raise InvitationNotSendable("Invitation sending is disabled")
    provider.verify_sender_domain()
    provider.verify_quota()
    with conn.transaction():
        row = conn.execute(
            """select kind, owner_id, workspace_id, email_digest, state, idempotency_key
                 from private.trial_invitation_deliveries where id = %s for update""",
            (delivery_id,),
        ).fetchone()
        if not row or row[:4] != (target.kind, target.owner_id, target.workspace_id, target.digest):
            raise InvitationNotSendable("Invitation reservation does not match recipient")
        if row[4] != "prepared":
            raise InvitationNotSendable("Invitation was already attempted")
        conn.execute(
            """update private.trial_invitation_deliveries
                  set state = 'attempting', attempted_at = clock_timestamp(),
                      updated_at = clock_timestamp()
                where id = %s""",
            (delivery_id,),
        )
        idempotency_key = row[5]
    # From this point, a timeout or crash leaves a durable 'attempting' row.
    # Operators reconcile with Resend; they never blindly retry.
    try:
        with conn.transaction():
            # This same advisory lock is used by the opt-out RPC. A preference
            # change that arrives first wins; a later one waits until dispatch ends.
            conn.execute(
                "select pg_advisory_xact_lock(hashtextextended(%s, 0))",
                (target.digest.hex(),),
            )
            opted_out = conn.execute(
                "select 1 from private.trial_invitation_opt_outs where email_digest = %s",
                (target.digest,),
            ).fetchone()
            other_attempt = conn.execute(
                """select 1 from private.trial_invitation_deliveries
                    where campaign = %s and email_digest = %s and id <> %s
                      and state <> 'prepared'""",
                (CAMPAIGN, target.digest, delivery_id),
            ).fetchone()
            if opted_out or other_attempt or not _current_eligibility(conn, target):
                raise InvitationNotSendable("Recipient is no longer eligible or has opted out")
            # Check Resend suppressions immediately before the external call.
            suppressed = provider.suppressed_digests()
            if target.digest.hex() in suppressed:
                raise InvitationNotSendable("Recipient is suppressed by the provider")
            conn.execute(
                """update private.trial_invitation_deliveries
                      set suppression_verified_at = clock_timestamp(),
                          eligibility_verified_at = clock_timestamp(), updated_at = clock_timestamp()
                    where id = %s and state = 'attempting'""",
                (delivery_id,),
            )
            email = render_trial_invitation(
                first_name=target.first_name, unsubscribe_url=make_opt_out_url(delivery_id)
            )
            message_id = sender.send_email(
                recipient=target.email, email=email, idempotency_key=str(idempotency_key)
            )
            conn.execute(
                """update private.trial_invitation_deliveries
                      set state = 'accepted', provider_message_id = %s,
                          accepted_at = clock_timestamp(), updated_at = clock_timestamp()
                    where id = %s and state = 'attempting'""",
                (message_id, delivery_id),
            )
    except Exception as exc:
        with conn.transaction():
            conn.execute(
                """update private.trial_invitation_deliveries
                      set state = 'uncertain', provider_error_code = 'send_unconfirmed',
                          updated_at = clock_timestamp() where id = %s and state = 'attempting'""",
                (delivery_id,),
            )
        raise InvitationNotSendable("Delivery was not confirmed; do not retry") from exc
    return message_id


def reconcile_delivery(conn: Any, delivery_id: UUID, provider: TrialInvitationProvider) -> str:
    """Record Resend's last event; API acceptance alone never means delivered."""
    row = conn.execute(
        "select provider_message_id from private.trial_invitation_deliveries where id = %s",
        (delivery_id,),
    ).fetchone()
    if not row or not row[0]:
        raise InvitationNotSendable("No provider message ID available for reconciliation")
    payload = provider._get(f"/emails/{row[0]}")
    if payload.get("id") != row[0]:
        raise InvitationProviderNotReady("Resend returned a different message")
    event = payload.get("last_event")
    state = {"delivered": "delivered", "bounced": "bounced", "complained": "complained"}.get(event)
    if state:
        with conn.transaction():
            conn.execute(
                """update private.trial_invitation_deliveries
                      set state = %s, last_event_at = clock_timestamp(),
                          delivered_at = case when %s = 'delivered' then clock_timestamp()
                            else delivered_at end,
                          updated_at = clock_timestamp()
                    where id = %s and provider_message_id = %s""",
                (state, state, delivery_id, row[0]),
            )
    return state or "accepted"
