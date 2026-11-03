"""Private aggregate preview of existing-user invitation candidates; never sends."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import stat

from app.jobs.trial_invitation_candidates import CANDIDATE_SQL, classify_candidates
from scripts.send_trial_test_invitation import _is_production_connection


def load_suppressions(path: Path | None) -> set[str] | None:
    if path is None:
        return None
    if path.is_symlink() or stat.S_IMODE(path.stat().st_mode) != 0o600:
        raise ValueError('Suppression snapshot must be a private mode-0600 regular file')
    data = json.loads(path.read_text())
    verified_at = datetime.fromisoformat(data['verified_at'])
    age = datetime.now(timezone.utc) - verified_at
    if data.get('source') != 'resend' or not 0 <= age.total_seconds() <= 3600:
        raise ValueError('A current, Resend-verified suppression snapshot is required')
    hashes = data['email_sha256']
    if not isinstance(hashes, list) or any(
        not isinstance(value, str) or len(value) != 64
        or any(char not in '0123456789abcdef' for char in value)
        for value in hashes
    ):
        raise ValueError('Invalid hashed suppression list')
    return set(hashes)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--suppression-snapshot', type=Path,
                        help='Private, recently verified Resend suppression digests')
    args = parser.parse_args()
    dsn = os.environ.get('GRAVITYOS_TRIAL_INVITE_DSN')
    if not dsn:
        parser.error('GRAVITYOS_TRIAL_INVITE_DSN is required')
    try:
        import psycopg
        from psycopg.conninfo import conninfo_to_dict
        options = conninfo_to_dict(dsn)
        if not _is_production_connection(options):
            raise ValueError('Expected the verified production PostgreSQL connection')
        suppressions = load_suppressions(args.suppression_snapshot)
        with psycopg.connect(dsn, connect_timeout=12,
                             options='-c default_transaction_read_only=on -c statement_timeout=30000') as conn:
            with conn.transaction():
                conn.execute('set transaction isolation level repeatable read, read only')
                rows = conn.execute(CANDIDATE_SQL).fetchall()
        recipients, counts = classify_candidates(rows, suppressed_digests=suppressions)
    except Exception:
        # Connection and provider errors may contain credentials or addresses.
        parser.exit(1, 'Recipient preview failed; inspect private operator diagnostics.\n')
    print(json.dumps({
        'checked_at': datetime.now(timezone.utc).isoformat(),
        'candidate_rows': len(rows),
        'exclusions_and_selection': counts,
        'suppression_verified': suppressions is not None,
        'preview_only_count': len(recipients) if suppressions is not None else None,
        'customer_send_authorized': False,
    }, sort_keys=True))


if __name__ == '__main__':
    main()
