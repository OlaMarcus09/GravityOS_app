"""Supabase JWT verification (ARCHITECTURE.md section 1 auth flow).

The browser authenticates with Supabase Auth and sends the access token as
`Authorization: Bearer <token>`. We verify the signature and expiry, then
expose the resulting user to route handlers.

Supabase now issues asymmetric (ES256) access tokens by default, verified
against the project's public JWKS. Legacy projects sign symmetrically (HS256)
with the shared JWT secret. We support both: the token header's `alg` decides
which path to use.
"""
from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

import httpx
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt

from app.core.config import get_settings

_bearer = HTTPBearer(auto_error=True)


@dataclass
class AuthContext:
    """The verified caller and the raw token (needed for user-scoped DB calls)."""

    user_id: str
    email: str | None
    token: str


@lru_cache
def _jwks() -> dict:
    """Fetch and cache the project's public signing keys (asymmetric tokens)."""
    settings = get_settings()
    url = f"{settings.supabase_url}/auth/v1/.well-known/jwks.json"
    resp = httpx.get(url, timeout=10.0)
    resp.raise_for_status()
    return resp.json()


def _signing_key(kid: str) -> dict:
    for key in _jwks().get("keys", []):
        if key.get("kid") == kid:
            return key
    # Key rotation: bust the cache once and retry before giving up.
    _jwks.cache_clear()
    for key in _jwks().get("keys", []):
        if key.get("kid") == kid:
            return key
    raise JWTError(f"no signing key for kid={kid}")


def verify_token(token: str) -> dict:
    settings = get_settings()
    try:
        header = jwt.get_unverified_header(token)
        alg = header.get("alg", "")
        if alg.startswith("HS"):
            key = settings.supabase_jwt_secret
            algorithms = ["HS256"]
        else:
            key = _signing_key(header.get("kid", ""))
            algorithms = [alg]
        return jwt.decode(
            token,
            key,
            algorithms=algorithms,
            audience=settings.jwt_audience,
        )
    except JWTError as exc:  # signature, expiry, audience, etc.
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": {"code": "invalid_token", "message": str(exc)}},
        ) from exc


def get_auth_context(
    creds: HTTPAuthorizationCredentials = Depends(_bearer),
) -> AuthContext:
    payload = verify_token(creds.credentials)
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": {"code": "invalid_token", "message": "missing sub claim"}},
        )
    return AuthContext(
        user_id=user_id,
        email=payload.get("email"),
        token=creds.credentials,
    )
