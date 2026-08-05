"""Minimal Soundcharts client foundation.

The client is intentionally not wired to a route or polling job. The first
modeled call is Soundcharts' aggregated current artist statistics endpoint:
GET /api/v2/artist/{uuid}/current/stats.
"""
from __future__ import annotations

from typing import Any

import httpx

from app.core.config import get_settings


SOUNDCHARTS_BASE_URL = "https://customer.api.soundcharts.com"


class SoundchartsNotConfiguredError(RuntimeError):
    """Raised when the deferred client is called without credentials."""


class SoundchartsClient:
    def __init__(
        self,
        *,
        app_id: str | None = None,
        api_key: str | None = None,
        http_client: httpx.Client | None = None,
    ) -> None:
        settings = get_settings()
        self.app_id = app_id if app_id is not None else settings.soundcharts_app_id
        self.api_key = api_key if api_key is not None else settings.soundcharts_api_key
        self._owns_client = http_client is None
        self.http = http_client or httpx.Client(base_url=SOUNDCHARTS_BASE_URL, timeout=20.0)

    def close(self) -> None:
        if self._owns_client:
            self.http.close()

    def __enter__(self) -> "SoundchartsClient":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def _headers(self) -> dict[str, str]:
        if not self.app_id or not self.api_key:
            raise SoundchartsNotConfiguredError(
                "SOUNDCHARTS_APP_ID and SOUNDCHARTS_API_KEY must be configured"
            )
        return {"x-app-id": self.app_id, "x-api-key": self.api_key}

    def get_artist_stats(self, soundcharts_uuid: str, *, period_days: int = 7) -> dict[str, Any]:
        """Return aggregated current stats without persisting or transforming them."""
        if period_days < 1:
            raise ValueError("period_days must be at least 1")
        response = self.http.get(
            f"/api/v2/artist/{soundcharts_uuid}/current/stats",
            params={"period": period_days},
            headers=self._headers(),
        )
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict):
            raise ValueError("Soundcharts current stats response must be an object")
        return payload


def get_artist_stats(soundcharts_uuid: str, *, period_days: int = 7) -> dict[str, Any]:
    """Convenience wrapper for the deferred current-stats client."""
    with SoundchartsClient() as client:
        return client.get_artist_stats(soundcharts_uuid, period_days=period_days)
