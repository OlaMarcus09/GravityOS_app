"""Fixed-campaign, operator-only delivery of existing-user trial invitations."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from hashlib import sha256
from hmac import new as hmac_new
from time import sleep
from typing import Any, Callable
from uuid import UUID

from app.integrations.resend import ResendClient
from app.integrations.trial_invitation_provider import TrialInvitationProvider
from app.jobs.trial_invitation_candidates import CANDIDATE_SQL, classify_candidates
from app.jobs.trial_invitation_delivery import (
    CAMPAIGN,
    InvitationTarget,
    deliver_prepared,
    prepare_invitation,
)

MAX_RECIPIENTS = 25
MIN_INTERVAL_SECONDS = 1.0


@dataclass(frozen=True)
class BatchItem:
    target: InvitationTarget
    prepared_id: UUID | None = None


@dataclass(frozen=True)
class BatchPreview:
    candidate_count: int
    counts: dict[str, int]
    window_active: bool
    sendable: tuple[BatchItem, ...]

    def scope(self, key: bytes) -> str:
        if len(key) < 32:
            raise ValueError('A private scope signing key is required')
        identities = sorted(f'{item.target.owner_id}:{item.target.digest.hex()}'
                            for item in self.sendable)
        payload = (CAMPAIGN + '\n' + '\n'.join(identities)).encode()
        return hmac_new(key, payload, sha256).hexdigest()

    def aggregate(self, key: bytes) -> dict[str, Any]:
        return {
            "campaign": CAMPAIGN,
            "candidate_owners": self.candidate_count,
            "exclusions": self.counts,
            "window_active": self.window_active,
            "currently_sendable": len(self.sendable),
            "scope": self.scope(key),
        }


def preview_batch(conn: Any, provider: TrialInvitationProvider) -> BatchPreview:
    """Read current identities privately; return only aggregates to the operator."""
    provider.verify_sender_domain()
    provider.verify_quota()
    suppressed = provider.suppressed_digests()
    window = conn.execute(
        """select enabled and starts_at is not null
                     and clock_timestamp() >= starts_at
                     and clock_timestamp() < ends_at + interval '1 second'
             from private.existing_user_trial_campaign where singleton"""
    ).fetchone()
    rows = conn.execute(CANDIDATE_SQL).fetchall()
    candidates, initial_counts = classify_candidates(rows, suppressed_digests=suppressed)
    counts = Counter(initial_counts)
    existing = conn.execute(
        """select owner_id::text, workspace_id::text, encode(email_digest, 'hex'), kind, state, id
             from private.trial_invitation_deliveries
            where campaign = %s""",
        (CAMPAIGN,),
    ).fetchall()
    by_owner: dict[str, list[tuple]] = {}
    by_digest: dict[str, list[tuple]] = {}
    for row in existing:
        by_owner.setdefault(row[0], []).append(row)
        by_digest.setdefault(row[2], []).append(row)
    sendable: list[BatchItem] = []
    for candidate in candidates:
        matches = {row[5]: row for row in (
            by_owner.get(candidate.owner_id, []) + by_digest.get(candidate.email_digest, [])
        )}
        if matches:
            records = list(matches.values())
            if (len(records) == 1 and records[0][:5] ==
                    (candidate.owner_id, candidate.workspace_id, candidate.email_digest,
                     'initial', 'prepared')):
                prepared_id = records[0][5]
                counts['resumable_prepared'] += 1
            else:
                counts['previously_attempted_or_conflicting'] += 1
                continue
        else:
            prepared_id = None
        sendable.append(BatchItem(
            InvitationTarget(email=candidate.verified_email,
                             first_name=candidate.first_name,
                             owner_id=UUID(candidate.owner_id),
                             workspace_id=UUID(candidate.workspace_id), kind='initial'),
            prepared_id,
        ))
    # The selector's count includes candidates removed by ledger checks.
    counts.pop('selected_for_preview_only', None)
    return BatchPreview(len(rows), dict(counts), bool(window and window[0]), tuple(sendable))


def confirmation_for(count: int, scope: str) -> str:
    return f"SEND {CAMPAIGN} initial {count} {scope}"


def send_batch(
    conn: Any,
    provider: TrialInvitationProvider,
    sender: ResendClient,
    *,
    expected_count: int,
    expected_scope: str,
    confirmation: str,
    scope_key: bytes,
    sending_enabled: bool,
    batch_enabled: bool,
    sleep_fn: Callable[[float], None] = sleep,
) -> dict[str, Any]:
    """One bounded, sequential attempt. Any failure stops; no retry occurs."""
    if not sending_enabled or not batch_enabled:
        raise ValueError('Customer invitation sending is disabled')
    if expected_count < 1 or expected_count > MAX_RECIPIENTS:
        raise ValueError('Recipient count is outside the reviewed batch limit')
    if confirmation != confirmation_for(expected_count, expected_scope):
        raise ValueError('Campaign and recipient-scope confirmation does not match')
    preview = preview_batch(conn, provider)
    if (not preview.window_active or len(preview.sendable) != expected_count
            or preview.scope(scope_key) != expected_scope):
        raise ValueError('Claim window or current recipient scope changed')
    provider.verify_quota(required=expected_count)
    accepted = 0
    resumed = 0
    for index, item in enumerate(preview.sendable):
        try:
            delivery_id = item.prepared_id
            if delivery_id is None:
                reservation = prepare_invitation(conn, item.target)
                if reservation is None:
                    raise ValueError('A concurrent operator reserved this invitation')
                delivery_id = reservation[0]
            else:
                resumed += 1
            # Existing delivery code rechecks ownership, claims, preferences,
            # opt-outs, domain, quota and live suppressions immediately before
            # the provider call. The ledger lock allows only one attempt.
            deliver_prepared(conn, item.target, delivery_id, provider=provider, sender=sender)
            accepted += 1
        except Exception:
            return {"campaign": CAMPAIGN, "accepted_by_provider": accepted,
                    "resumed_prepared": resumed, "stopped": True,
                    "remaining_unattempted": expected_count - index - 1,
                    "reason": "Inspect the private ledger and reconcile before any further run"}
        if index + 1 < expected_count:
            sleep_fn(MIN_INTERVAL_SECONDS)
    return {"campaign": CAMPAIGN, "accepted_by_provider": accepted,
            "resumed_prepared": resumed, "stopped": False,
            "remaining_unattempted": 0,
            "delivery_verified": False}
