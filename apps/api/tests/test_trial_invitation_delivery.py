"""Invitation security boundaries: token, provider evidence, and no-resend ledger."""

from types import SimpleNamespace
from uuid import uuid4
from unittest.mock import Mock

import httpx
import pytest
from fastapi import HTTPException

from app.integrations.trial_invitation_provider import (
    InvitationProviderNotReady,
    TrialInvitationProvider,
)
from app.integrations.trial_invitation_tokens import (
    make_opt_out_token,
    make_opt_out_url,
    verify_opt_out_token,
)
from app.jobs.trial_invitation_delivery import (
    InvitationNotSendable,
    InvitationTarget,
    deliver_prepared,
    prepare_invitation,
)
from app.routers import trial_invitation_opt_out
from scripts.send_trial_test_invitation import _is_production_connection


def test_opt_out_token_is_opaque_single_purpose_and_tamper_resistant(monkeypatch):
    monkeypatch.setattr("app.integrations.trial_invitation_tokens._key", lambda: b"s" * 32)
    delivery_id = uuid4()
    token = make_opt_out_token(delivery_id)
    assert verify_opt_out_token(token) == delivery_id
    assert verify_opt_out_token(token[:-1] + ("0" if token[-1] != "0" else "1")) is None
    url = make_opt_out_url(delivery_id)
    assert "#token=" in url and "?token=" not in url
    assert "@" not in url


def test_unsubscribe_rejects_bad_token_before_service_access(monkeypatch):
    client = Mock()
    monkeypatch.setattr(trial_invitation_opt_out, "get_service_client", lambda: client)
    with pytest.raises(HTTPException) as error:
        trial_invitation_opt_out.unsubscribe(trial_invitation_opt_out.OptOutRequest(token="x" * 97))
    assert error.value.status_code == 400
    client.rpc.assert_not_called()


def test_unsubscribe_uses_service_only_rpc_and_is_idempotent(monkeypatch):
    monkeypatch.setattr("app.integrations.trial_invitation_tokens._key", lambda: b"s" * 32)
    client = Mock()
    client.rpc.return_value.execute.return_value = SimpleNamespace(data=True)
    monkeypatch.setattr(trial_invitation_opt_out, "get_service_client", lambda: client)
    delivery_id = uuid4()
    request = trial_invitation_opt_out.OptOutRequest(token=make_opt_out_token(delivery_id))
    assert trial_invitation_opt_out.unsubscribe(request) == {"unsubscribed": True}
    assert trial_invitation_opt_out.unsubscribe(request) == {"unsubscribed": True}
    client.rpc.assert_called_with("record_trial_invitation_opt_out", {"p_delivery_id": str(delivery_id)})


def _provider(handler):
    return TrialInvitationProvider("audit", httpx.Client(
        base_url="https://api.resend.com", transport=httpx.MockTransport(handler)
    ))


def test_provider_401_does_not_prove_domain_or_suppression_readiness():
    provider = _provider(lambda _: httpx.Response(401, json={"message": "Unauthorized"}))
    with pytest.raises(InvitationProviderNotReady):
        provider.verify_sender_domain()
    with pytest.raises(InvitationProviderNotReady):
        provider.suppressed_digests()


def test_provider_requires_verified_domain_and_complete_suppressions():
    def handler(request):
        if request.url.path == "/domains":
            return httpx.Response(200, json={"data": [{"id": "domain-id", "name": "gravityos.tech", "status": "verified",
                "capabilities": {"sending": "enabled"}}], "has_more": False})
        if request.url.path == "/domains/domain-id":
            return httpx.Response(200, json={"name": "gravityos.tech", "status": "verified",
                "records": [{"record": "SPF", "status": "verified"},
                            {"record": "DKIM", "status": "verified"}]})
        if request.url.path == "/usage":
            return httpx.Response(200, json={"emails": {
                "daily": {"used": 0, "limit": 100},
                "monthly": {"used": 0, "limit": 3000}}})
        return httpx.Response(200, json={"data": [{"email": "blocked@example.com"}],
                                         "has_more": False})
    provider = _provider(handler)
    provider.verify_sender_domain()
    provider.verify_quota()
    assert len(provider.suppressed_digests()) == 1

    incomplete = _provider(lambda _: httpx.Response(200, json={"data": [], "has_more": True}))
    with pytest.raises(InvitationProviderNotReady):
        incomplete.suppressed_digests()


def test_test_delivery_is_hard_limited_to_founder_inbox():
    with pytest.raises(InvitationNotSendable):
        prepare_invitation(Mock(), InvitationTarget(email="someone@example.com"))


def test_disabled_sending_never_calls_provider_or_resend(monkeypatch):
    monkeypatch.setattr("app.jobs.trial_invitation_delivery.get_settings",
                        lambda: SimpleNamespace(trial_invitation_sending_enabled=False))
    provider, sender = Mock(), Mock()
    with pytest.raises(InvitationNotSendable):
        deliver_prepared(Mock(), InvitationTarget(email="highmarcus.eth@gmail.com"),
                         uuid4(), provider=provider, sender=sender)
    provider.verify_sender_domain.assert_not_called()
    sender.send_email.assert_not_called()


def test_test_sender_accepts_only_verified_production_database_routes():
    base = {"dbname": "postgres", "sslmode": "require", "port": "5432"}
    assert _is_production_connection({**base, "host": "db.hopleyvbxiuksxxucozg.supabase.co",
                                      "user": "postgres"})
    assert _is_production_connection({**base, "host": "aws-0-eu-central-1.pooler.supabase.com",
                                      "user": "postgres.hopleyvbxiuksxxucozg"})
    assert not _is_production_connection({**base, "host": "aws-0-eu-central-1.pooler.supabase.com",
                                          "user": "postgres.otherproject"})
    assert not _is_production_connection({**base, "host": "db.hopleyvbxiuksxxucozg.supabase.co",
                                          "user": "postgres", "hostaddr": "127.0.0.1"})
    assert not _is_production_connection({**base, "host": "db.hopleyvbxiuksxxucozg.supabase.co",
                                          "user": "postgres", "dbname": "other"})
