"""Private operator command. Preview by default; customer sending requires new approval."""

from __future__ import annotations

import argparse
import json
import os

from app.core.config import get_settings
from app.integrations.resend import ResendClient
from app.integrations.trial_invitation_provider import TrialInvitationProvider
from app.jobs.trial_invitation_batch import (
    MAX_RECIPIENTS,
    confirmation_for,
    preview_batch,
    send_batch,
)
from app.jobs.trial_invitation_delivery import CAMPAIGN, reconcile_delivery
from scripts.send_trial_test_invitation import _is_production_connection


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--campaign', required=True)
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument('--send', action='store_true')
    modes.add_argument('--reconcile', action='store_true')
    parser.add_argument('--expected-count', type=int)
    parser.add_argument('--scope', default='')
    parser.add_argument('--confirm', default='')
    args = parser.parse_args()
    if args.campaign != CAMPAIGN:
        parser.error('Only the reviewed existing-user trial campaign is supported')
    settings = get_settings()
    dsn = os.environ.get('GRAVITYOS_TRIAL_INVITE_DSN', '')
    audit_key = os.environ.get('RESEND_AUDIT_API_KEY', '')
    if not dsn or not audit_key:
        parser.error('Private production DSN and Resend audit credential are required')
    if args.send:
        if (args.expected_count is None or not args.scope
                or args.confirm != confirmation_for(args.expected_count, args.scope)
                or not settings.trial_invitation_sending_enabled
                or not settings.trial_invitation_customer_batch_enabled
                or not settings.resend_api_key
                or settings.email_from != 'Gravity OS <notifications@gravityos.tech>'
                or len(settings.trial_invitation_signing_key.encode()) < 32):
            parser.error('Customer send authorization or configuration is incomplete')
    elif args.expected_count is not None or args.scope or args.confirm:
        parser.error('Count, scope and confirmation are valid only with --send')
    try:
        import psycopg
        from psycopg.conninfo import conninfo_to_dict

        if not _is_production_connection(conninfo_to_dict(dsn)):
            raise ValueError('Expected the verified production PostgreSQL connection')
        with psycopg.connect(dsn, connect_timeout=12, autocommit=True) as conn:
            with TrialInvitationProvider(audit_key) as provider:
                if args.reconcile:
                    rows = conn.execute(
                        """select id from private.trial_invitation_deliveries
                            where campaign = %s and kind = 'initial'
                              and provider_message_id is not null
                              and state in ('accepted', 'delivered')
                            order by created_at limit %s""",
                        (CAMPAIGN, MAX_RECIPIENTS),
                    ).fetchall()
                    counts: dict[str, int] = {}
                    for (delivery_id,) in rows:
                        state = reconcile_delivery(conn, delivery_id, provider)
                        counts[state] = counts.get(state, 0) + 1
                    output = {'campaign': CAMPAIGN, 'reconciled': len(rows), 'states': counts,
                              'email_sent': False}
                elif args.send:
                    with ResendClient() as sender:
                        output = send_batch(
                            conn, provider, sender, expected_count=args.expected_count,
                            expected_scope=args.scope,
                            confirmation=args.confirm,
                            scope_key=settings.trial_invitation_signing_key.encode(),
                            sending_enabled=settings.trial_invitation_sending_enabled,
                            batch_enabled=settings.trial_invitation_customer_batch_enabled,
                        )
                    output['provider_acceptance_is_delivery'] = False
                else:
                    output = preview_batch(conn, provider).aggregate(
                        settings.trial_invitation_signing_key.encode())
                    output['email_sent'] = False
    except Exception:
        # Provider and database exceptions can contain addresses or credentials.
        parser.exit(1, 'Invitation operation stopped. Inspect the private ledger; do not retry uncertain sends.\n')
    print(json.dumps(output, sort_keys=True))
    if output.get('stopped'):
        parser.exit(1)


if __name__ == '__main__':
    main()
