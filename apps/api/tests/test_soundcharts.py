from __future__ import annotations

import httpx
import pytest

from app.integrations.soundcharts import SoundchartsClient, SoundchartsNotConfiguredError


def test_current_artist_stats_uses_soundcharts_auth_and_default_period():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/v2/artist/artist-uuid/current/stats"
        assert request.url.params["period"] == "7"
        assert request.headers["x-app-id"] == "app-id"
        assert request.headers["x-api-key"] == "api-key"
        return httpx.Response(200, json={"social": [], "streaming": []})

    http = httpx.Client(
        base_url="https://customer.api.soundcharts.com",
        transport=httpx.MockTransport(handler),
    )
    client = SoundchartsClient(app_id="app-id", api_key="api-key", http_client=http)

    assert client.get_artist_stats("artist-uuid") == {
        "social": [],
        "streaming": [],
    }


def test_current_artist_stats_requires_both_credentials():
    http = httpx.Client(
        base_url="https://customer.api.soundcharts.com",
        transport=httpx.MockTransport(lambda _: httpx.Response(200, json={})),
    )
    client = SoundchartsClient(app_id="", api_key="", http_client=http)

    with pytest.raises(SoundchartsNotConfiguredError):
        client.get_artist_stats("artist-uuid")


def test_current_artist_stats_rejects_invalid_period_without_calling_api():
    client = SoundchartsClient(app_id="app-id", api_key="api-key")
    try:
        with pytest.raises(ValueError, match="period_days"):
            client.get_artist_stats("artist-uuid", period_days=0)
    finally:
        client.close()
