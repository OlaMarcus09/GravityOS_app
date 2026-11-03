"""Read-only Resend checks. Any missing or malformed evidence blocks sending."""

from __future__ import annotations

from hashlib import sha256

import httpx

from app.integrations.resend import RESEND_BASE_URL


class InvitationProviderNotReady(RuntimeError):
    pass


class TrialInvitationProvider:
    def __init__(self, audit_key: str, http_client: httpx.Client | None = None) -> None:
        self.audit_key = audit_key
        self._owns_http = http_client is None
        self.http = http_client or httpx.Client(base_url=RESEND_BASE_URL, timeout=20.0)

    def _get(self, path: str) -> dict:
        if not self.audit_key:
            raise InvitationProviderNotReady("Resend audit credential is missing")
        try:
            response = self.http.get(path, headers={"Authorization": f"Bearer {self.audit_key}"})
            response.raise_for_status()
            result = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            # Do not include response bodies: provider diagnostics may contain PII.
            raise InvitationProviderNotReady("Resend verification is unavailable") from exc
        if not isinstance(result, dict):
            raise InvitationProviderNotReady("Resend verification response is invalid")
        return result

    def verify_sender_domain(self) -> None:
        result = self._get("/domains")
        domains = result.get("data")
        if result.get("has_more") is not False or not isinstance(domains, list):
            raise InvitationProviderNotReady("Resend domain list is incomplete")
        matching = [d for d in domains if isinstance(d, dict) and d.get("name") == "gravityos.tech"]
        if len(matching) != 1:
            raise InvitationProviderNotReady("GravityOS sender domain is not visible")
        domain = matching[0]
        capabilities = domain.get("capabilities")
        if (domain.get("status") != "verified" or not isinstance(capabilities, dict)
                or capabilities.get("sending") != "enabled"):
            raise InvitationProviderNotReady("GravityOS sender domain is not verified for sending")
        domain_id = domain.get("id")
        if not isinstance(domain_id, str) or not domain_id:
            raise InvitationProviderNotReady("Resend domain ID is missing")
        detail = self._get(f"/domains/{domain_id}")
        if detail.get("name") != "gravityos.tech" or detail.get("status") != "verified":
            raise InvitationProviderNotReady("Resend domain detail is inconsistent")
        records = detail.get("records")
        if not isinstance(records, list):
            raise InvitationProviderNotReady("Resend DNS verification is unavailable")
        for record_type in ("SPF", "DKIM"):
            relevant = [r for r in records if isinstance(r, dict) and r.get("record") == record_type]
            if not relevant or any(r.get("status") != "verified" for r in relevant):
                raise InvitationProviderNotReady(f"Resend {record_type} verification is incomplete")

    def suppressed_digests(self) -> set[str]:
        result = self._get("/suppressions")
        entries = result.get("data")
        if result.get("has_more") is not False or not isinstance(entries, list):
            raise InvitationProviderNotReady("Resend suppression list is incomplete")
        digests: set[str] = set()
        for entry in entries:
            if not isinstance(entry, dict) or not isinstance(entry.get("email"), str):
                raise InvitationProviderNotReady("Resend suppression list is malformed")
            normalized = entry["email"].strip().lower()
            if "@" not in normalized:
                raise InvitationProviderNotReady("Resend suppression list is malformed")
            digests.add(sha256(normalized.encode()).hexdigest())
        return digests

    def verify_quota(self, required: int = 1) -> None:
        result = self._get("/usage")
        emails = result.get("emails")
        if not isinstance(emails, dict):
            raise InvitationProviderNotReady("Resend quota is unavailable")
        for period in ("daily", "monthly"):
            bucket = emails.get(period)
            if not isinstance(bucket, dict) or not isinstance(bucket.get("used"), int):
                raise InvitationProviderNotReady("Resend quota is unavailable")
            limit = bucket.get("limit")
            if limit is not None and (not isinstance(limit, int) or limit - bucket["used"] < required):
                raise InvitationProviderNotReady("Resend quota is exhausted")

    def close(self) -> None:
        if self._owns_http:
            self.http.close()

    def __enter__(self) -> TrialInvitationProvider:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()
