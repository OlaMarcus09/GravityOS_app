"""Supabase client factories (ARCHITECTURE.md section 1).

Two clients:
- `get_user_client(token)`: authenticated as the end user. Postgres requests
  run under that user's JWT so RLS applies — this is the default path.
- `get_service_client()`: service-role key, bypasses RLS. Reserved for the
  service-owned writes called out in section 2 (gravity_scores, ai_outputs).
"""
from __future__ import annotations

from functools import lru_cache

import httpx
from supabase import Client, create_client

from app.core.config import get_settings


def _force_http1(client: Client) -> Client:
    """Rebuild the PostgREST session on HTTP/1.1.

    Supabase sends an HTTP/2 GOAWAY on reused keep-alive connections, which
    httpx surfaces as RemoteProtocolError(ConnectionTerminated) on the second
    query of a request. Pinning HTTP/1.1 avoids the broken connection reuse.
    """
    session = client.postgrest.session
    client.postgrest.session = httpx.Client(
        base_url=session.base_url,
        headers=session.headers,
        timeout=session.timeout,
        http2=False,
    )
    return client


def get_user_client(access_token: str) -> Client:
    """A Supabase client that acts as the authenticated user (RLS enforced)."""
    settings = get_settings()
    client = create_client(settings.supabase_url, settings.supabase_anon_key)
    _force_http1(client)
    # Attach the user's JWT so PostgREST evaluates RLS as that user.
    client.postgrest.auth(access_token)
    return client


@lru_cache
def get_service_client() -> Client:
    """Service-role client (bypasses RLS). Use sparingly."""
    settings = get_settings()
    return _force_http1(create_client(settings.supabase_url, settings.supabase_service_role_key))
