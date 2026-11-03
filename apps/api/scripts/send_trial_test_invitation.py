"""Dry-run by default; one explicitly authorized founder test inbox only."""

from __future__ import annotations

import argparse
import os

from app.core.config import get_settings
from app.integrations.resend import ResendClient
from app.integrations.trial_invitation import render_trial_invitation
from app.integrations.trial_invitation_provider import TrialInvitationProvider
from app.jobs.trial_invitation_delivery import (
    InvitationTarget,
    deliver_prepared,
    prepare_invitation,
)


def _is_production_connection(opts: dict[str, str]) -> bool:
    """Allow only this project's direct or verified session-pooler connection."""
    if (opts.get("dbname") != "postgres" or opts.get("sslmode") != "require"
            or opts.get("port") != "5432" or opts.get("hostaddr")
            or opts.get("service") or opts.get("servicefile")):
        return False
    return (opts.get("host"), opts.get("user")) in {
        ("db.hopleyvbxiuksxxucozg.supabase.co", "postgres"),
        ("aws-0-eu-central-1.pooler.supabase.com", "postgres.hopleyvbxiuksxxucozg"),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--send-authorized-test", action="store_true")
    args = parser.parse_args()
    if not args.send_authorized_test:
        sample = render_trial_invitation(
            first_name="Alex",
            unsubscribe_url="https://www.gravityos.tech/trial-invitations/unsubscribe#token=SYNTHETIC",
        )
        print({"mode": "synthetic_dry_run", "subject": sample.subject,
               "html_bytes": len(sample.html), "text_bytes": len(sample.text),
               "customer_send": False})
        return

    settings = get_settings()
    dsn = os.environ.get("GRAVITYOS_TRIAL_INVITE_DSN", "")
    audit_key = os.environ.get("RESEND_AUDIT_API_KEY", "")
    if not all((dsn, audit_key, settings.resend_api_key,
                settings.trial_invitation_sending_enabled,
                len(settings.trial_invitation_signing_key.encode()) >= 32,
                settings.email_from == "Gravity OS <notifications@gravityos.tech>")):
        parser.exit(1, "Test send prerequisites are incomplete. No email sent.\n")
    try:
        import psycopg
        from psycopg.conninfo import conninfo_to_dict

        opts = conninfo_to_dict(dsn)
        if not _is_production_connection(opts):
            raise ValueError("Expected production database with SSL")
        target = InvitationTarget(email="highmarcus.eth@gmail.com", first_name="Marcus")
        with TrialInvitationProvider(audit_key) as provider:
            provider.verify_sender_domain()
            provider.verify_quota()
            if target.digest.hex() in provider.suppressed_digests():
                raise ValueError("Test inbox is suppressed")
            with psycopg.connect(dsn, connect_timeout=12, autocommit=True) as conn:
                reservation = prepare_invitation(conn, target)
                if reservation is None:
                    raise ValueError("Test invitation was already reserved; no second send")
                with ResendClient() as sender:
                    message_id = deliver_prepared(
                        conn, target, reservation[0], provider=provider, sender=sender
                    )
        print({"mode": "authorized_test", "provider_accepted": True,
               "message_id": message_id, "delivery_status": "not_yet_verified",
               "customer_send": False})
    except Exception:
        # Do not print exception bodies: they may contain connection details or PII.
        parser.exit(1, "Test send stopped. Inspect private operator diagnostics.\n")


if __name__ == "__main__":
    main()
