"""One-time operator batch safety without external email or production data."""

from hashlib import sha256
from types import SimpleNamespace
from unittest.mock import Mock
from uuid import uuid4

import pytest

from app.jobs import trial_invitation_batch as batch


KEY = b's' * 32
ORIGINAL_PREVIEW = batch.preview_batch
OWNER = uuid4()
WORKSPACE = uuid4()
ADDRESS = 'owner@example.com'
DIGEST = sha256(ADDRESS.encode()).hexdigest()


class FakeConnection:
    def __init__(self, rows, ledger=(), active=True):
        self.rows = rows
        self.ledger = ledger
        self.active = active

    def execute(self, sql, params=None):
        if 'from private.existing_user_trial_campaign' in sql:
            return SimpleNamespace(fetchone=lambda: (self.active,))
        if 'from private.trial_invitation_deliveries' in sql:
            return SimpleNamespace(fetchall=lambda: self.ledger)
        return SimpleNamespace(fetchall=lambda: self.rows)


def candidate(email=ADDRESS, reason='eligible', preference=True):
    return (str(OWNER), str(WORKSPACE), email, 'Ada Lovelace', preference, reason)


def provider(suppressed=()):
    result = Mock()
    result.suppressed_digests.return_value = set(suppressed)
    return result


def preview(rows=None, ledger=(), suppressed=(), active=True):
    return ORIGINAL_PREVIEW(FakeConnection(rows or [candidate()], ledger, active),
                            provider(suppressed))


def test_preview_excludes_ineligible_suppressed_duplicate_and_prior_test_delivery():
    rows = [candidate(), candidate(' OWNER@EXAMPLE.COM '),
            candidate('claimed@example.com', 'already_claimed'),
            candidate('paid@example.com', 'paid_workspace_conflict'),
            candidate('unconfirmed@example.com', 'email_confirmation_required'),
            candidate('opted@example.com', 'promotional_opt_out'),
            candidate('disabled@example.com', preference=False)]
    result = preview(rows)
    assert result.aggregate(KEY)['currently_sendable'] == 1
    assert result.counts['duplicate_email'] == 1
    for reason in ('already_claimed', 'paid_workspace_conflict',
                   'email_confirmation_required', 'promotional_opt_out', 'email_disabled'):
        assert result.counts[reason] == 1
    assert preview([candidate()], suppressed={DIGEST}).sendable == ()
    delivered_test = (str(OWNER), str(WORKSPACE), DIGEST, 'test', 'delivered', uuid4())
    assert preview([candidate()], ledger=[delivered_test]).sendable == ()


def test_prepared_resumes_but_attempted_and_uncertain_never_retry():
    delivery_id = uuid4()
    prepared = (str(OWNER), str(WORKSPACE), DIGEST, 'initial', 'prepared', delivery_id)
    assert preview(ledger=[prepared]).sendable[0].prepared_id == delivery_id
    for state in ('attempting', 'accepted', 'delivered', 'failed', 'uncertain'):
        row = (str(OWNER), str(WORKSPACE), DIGEST, 'initial', state, delivery_id)
        assert preview(ledger=[row]).sendable == ()


def test_scope_changes_when_recipient_changes_and_contains_no_address():
    first = preview()
    second = preview([candidate('other@example.com')])
    assert first.scope(KEY) != second.scope(KEY)
    assert ADDRESS not in str(first.aggregate(KEY))
    with pytest.raises(ValueError):
        first.scope(b'short')


def send(monkeypatch, *, enabled=True, batch_enabled=True, active=True,
         count=1, scope=None, confirmation=None, quota_error=None):
    current = preview(active=active)
    scope = scope or current.scope(KEY)
    monkeypatch.setattr(batch, 'preview_batch', lambda *_: current)
    p = provider()
    if quota_error:
        p.verify_quota.side_effect = quota_error
    return batch.send_batch(
        Mock(), p, Mock(), expected_count=count, expected_scope=scope,
        confirmation=confirmation or batch.confirmation_for(count, scope),
        scope_key=KEY, sending_enabled=enabled, batch_enabled=batch_enabled,
        sleep_fn=lambda _: None,
    )


def test_disabled_invalid_confirmation_changed_scope_and_expired_window_stop_before_send(monkeypatch):
    for kwargs in ({'enabled': False}, {'batch_enabled': False},
                   {'confirmation': 'SEND'}, {'scope': '0' * 64},
                   {'active': False}, {'count': 2}):
        with pytest.raises(ValueError):
            send(monkeypatch, **kwargs)


def test_quota_failure_prevents_reservation(monkeypatch):
    reserve = Mock()
    monkeypatch.setattr(batch, 'prepare_invitation', reserve)
    with pytest.raises(RuntimeError):
        send(monkeypatch, quota_error=RuntimeError('quota exhausted'))
    reserve.assert_not_called()


def test_partial_failure_stops_without_automatic_retry(monkeypatch):
    monkeypatch.setattr(batch, 'prepare_invitation', lambda *_: (uuid4(), uuid4()))
    deliver = Mock(side_effect=TimeoutError('ambiguous provider response'))
    monkeypatch.setattr(batch, 'deliver_prepared', deliver)
    result = send(monkeypatch)
    assert result['stopped'] is True
    assert result['accepted_by_provider'] == 0
    assert deliver.call_count == 1
    assert 'ambiguous provider response' not in str(result)


def test_concurrent_reservation_conflict_stops_without_send(monkeypatch):
    monkeypatch.setattr(batch, 'prepare_invitation', lambda *_: None)
    deliver = Mock()
    monkeypatch.setattr(batch, 'deliver_prepared', deliver)
    assert send(monkeypatch)['stopped'] is True
    deliver.assert_not_called()
