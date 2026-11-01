"""Request-time trial and paid entitlement boundaries."""
from datetime import datetime, timedelta, timezone

from app.services.entitlements import effective_plan, trial_status


NOW = datetime(2026, 10, 31, 12, 0, tzinfo=timezone.utc)


def workspace(**updates):
    row = {"plan": "free", "billing_status": "none", "trial_started_at": None,
           "trial_expires_at": None, "current_period_end": None}
    row.update(updates)
    return row


def test_seven_full_days_and_exact_expiry_boundary():
    start = NOW
    end = start + timedelta(hours=168)
    row = workspace(trial_started_at=start.isoformat(), trial_expires_at=end.isoformat())
    assert effective_plan(row, at=end - timedelta(microseconds=1)) == "pro"
    assert trial_status(row, at=end - timedelta(microseconds=1)) == "active"
    assert effective_plan(row, at=end) == "free"
    assert trial_status(row, at=end) == "expired"


def test_manual_grant_and_verified_paid_plan_take_precedence():
    ended = (NOW - timedelta(days=1)).isoformat()
    future = (NOW + timedelta(days=365)).isoformat()
    assert effective_plan(workspace(plan="team", billing_status="manual", trial_expires_at=ended), at=NOW) == "team"
    assert effective_plan(workspace(plan="pro", billing_status="active", current_period_end=future), at=NOW) == "pro"
    assert effective_plan(workspace(plan="pro", billing_status="active", current_period_end=ended), at=NOW) == "free"
    assert effective_plan(workspace(plan="pro", billing_status="none"), at=NOW) == "free"


def test_trial_never_overwrites_a_paid_or_manual_workspace():
    active_trial = workspace(trial_started_at=NOW.isoformat(), trial_expires_at=(NOW + timedelta(days=7)).isoformat())
    assert effective_plan({**active_trial, "plan": "pro", "billing_status": "manual"}, at=NOW) == "pro"
    assert trial_status({**active_trial, "plan": "pro", "billing_status": "manual"}, at=NOW) == "superseded"
    assert effective_plan({**active_trial, "plan": "team", "billing_status": "active", "current_period_end": (NOW + timedelta(days=365)).isoformat()}, at=NOW) == "team"
