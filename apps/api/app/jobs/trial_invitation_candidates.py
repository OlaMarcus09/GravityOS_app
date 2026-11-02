"""Private, read-only selection for an invitation preview. Never emits PII to logs."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from hashlib import sha256
from typing import Iterable

# Run using a read-only database transaction. A single owner gets at most one
# selected Free workspace; the production claim function enforces all other
# policy, including the campaign window and conflict across owned workspaces.
CANDIDATE_SQL = """
select u.id::text owner_id, w.id::text workspace_id, u.email,
       p.display_name, pref.email_enabled,
       private.existing_user_trial_status(u.id, w.id, clock_timestamp()) reason
from auth.users u
join lateral (
    select w.id from public.workspaces w
    join public.workspace_members m on m.workspace_id = w.id
         and m.user_id = u.id and m.role = 'owner'
    where w.owner_id = u.id and w.plan = 'free' and w.billing_status = 'none'
      and w.trial_started_at is null and w.trial_expires_at is null
    order by w.id limit 1
) w on true
left join public.profiles p on p.id = u.id
left join public.notification_preferences pref on pref.user_id = u.id
order by u.id
"""


@dataclass(frozen=True)
class Candidate:
    owner_id: str
    workspace_id: str
    verified_email: str
    first_name: str | None
    email_digest: str


def classify_candidates(
    rows: Iterable[tuple[str, str, str | None, str | None, bool | None, str]],
    *,
    suppressed_digests: set[str] | None,
) -> tuple[list[Candidate], dict[str, int]]:
    """Keep addresses only in memory and return aggregate exclusions."""
    recipients: list[Candidate] = []
    counts: Counter[str] = Counter()
    seen: set[str] = set()
    for owner_id, workspace_id, email, display_name, email_enabled, reason in rows:
        if reason != 'eligible':
            counts[reason] += 1
            continue
        if email_enabled is False:
            counts['email_disabled'] += 1
            continue
        normalized = (email or '').strip().lower()
        if not normalized or '@' not in normalized:
            counts['invalid_email'] += 1
            continue
        digest = sha256(normalized.encode('utf-8')).hexdigest()
        if digest in seen:
            counts['duplicate_email'] += 1
            continue
        seen.add(digest)
        if suppressed_digests is None:
            counts['pending_suppression_verification'] += 1
            continue
        if digest in suppressed_digests:
            counts['suppressed'] += 1
            continue
        parts = (display_name or '').strip().split(maxsplit=1)
        recipients.append(Candidate(
            owner_id=owner_id,
            workspace_id=workspace_id,
            verified_email=normalized,
            first_name=parts[0] if parts else None,
            email_digest=digest,
        ))
        counts['selected_for_preview_only'] += 1
    return recipients, dict(counts)
