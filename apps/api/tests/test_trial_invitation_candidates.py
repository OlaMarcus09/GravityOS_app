from hashlib import sha256

from app.jobs.trial_invitation_candidates import CANDIDATE_SQL, classify_candidates
from scripts.preview_trial_recipients import load_suppressions


def test_eligibility_preference_suppression_and_name_fallback():
    digest = sha256(b'owner@example.com').hexdigest()
    rows = [
        ('one', 'ws1', ' Owner@Example.com ', 'Ada Lovelace', True, 'eligible'),
        ('two', 'ws2', 'opted@example.com', 'Opted Out', False, 'eligible'),
        ('three', 'ws3', 'paid@example.com', None, True, 'paid_workspace_conflict'),
        ('four', 'ws4', 'unconfirmed@example.com', None, True, 'email_confirmation_required'),
        ('five', 'ws5', 'Owner@example.com', None, True, 'eligible'),
        ('six', 'ws6', 'neutral@example.com', None, None, 'eligible'),
    ]
    candidates, counts = classify_candidates(rows, suppressed_digests={digest})
    assert [c.verified_email for c in candidates] == ['neutral@example.com']
    assert candidates[0].first_name is None
    assert counts == {'suppressed': 1, 'email_disabled': 1, 'paid_workspace_conflict': 1,
                      'email_confirmation_required': 1, 'duplicate_email': 1,
                      'selected_for_preview_only': 1}


def test_missing_suppression_snapshot_fails_closed():
    candidates, counts = classify_candidates([
        ('one', 'ws1', 'owner@example.com', None, None, 'eligible')
    ], suppressed_digests=None)
    assert not candidates
    assert counts == {'pending_suppression_verification': 1}
    assert load_suppressions(None) is None


def test_query_rechecks_database_policy_and_owner_membership():
    assert "private.existing_user_trial_status(u.id, w.id, clock_timestamp())" in CANDIDATE_SQL
    assert "m.role = 'owner'" in CANDIDATE_SQL
    assert "w.billing_status = 'none'" in CANDIDATE_SQL
    assert "w.trial_started_at is null" in CANDIDATE_SQL
