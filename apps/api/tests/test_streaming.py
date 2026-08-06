from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import Mock, patch

import httpx
import pytest
from fastapi import HTTPException

from app.core.auth import AuthContext
from app.core.deps import WorkspaceContext
from app.routers.streaming import (
    _enforce_sync_cooldown,
    _snapshot_rows,
    get_artist_link,
    get_streaming_summary,
    sync_artist_stats,
)


def _query(data) -> Mock:
    query = Mock()
    for method in ("select", "eq", "order", "limit", "upsert"):
        getattr(query, method).return_value = query
    query.execute.return_value = Mock(data=data)
    return query


def _context(db: Mock) -> WorkspaceContext:
    return WorkspaceContext(
        workspace_id="workspace-1",
        role="member",
        plan="free",
        auth=AuthContext(user_id="user-1", email="user@example.com", token="token"),
        db=db,
    )


def test_snapshot_rows_maps_supported_current_stat_groups() -> None:
    rows = _snapshot_rows(
        {
            "social": [
                {"platform": "Instagram", "value": 1200, "date": "2026-08-06T00:00:00Z"},
                {"platform": "", "value": 4},
            ],
            "streaming": [{"platform": "Spotify", "value": 300.5}],
            "related": [{"platform": "ignored", "value": 1}],
        },
        workspace_id="workspace-1",
        artist_link_id="link-1",
        synced_at=datetime(2026, 8, 6, tzinfo=timezone.utc),
    )

    assert [(row["metric_type"], row["platform"], row["value"]) for row in rows] == [
        ("social", "instagram", 1200),
        ("streaming", "spotify", 300.5),
    ]
    assert rows[1]["captured_at"] == "2026-08-06T00:00:00+00:00"


def test_get_artist_link_returns_none_when_workspace_has_not_connected_one() -> None:
    db = Mock()
    db.table.return_value = _query([])

    assert get_artist_link(_context(db)) is None


def test_sync_cooldown_blocks_recent_workspace_snapshot() -> None:
    db = Mock()
    db.table.return_value = _query([{"captured_at": "2026-08-06T12:00:00Z"}])

    with pytest.raises(HTTPException) as exc_info:
        _enforce_sync_cooldown(
            _context(db),
            "link-1",
            datetime(2026, 8, 6, 12, 5, tzinfo=timezone.utc),
        )

    assert exc_info.value.status_code == 429
    assert exc_info.value.detail["error"]["code"] == "sync_cooldown"
    assert exc_info.value.headers["Retry-After"] == "600"


def test_sync_cooldown_allows_old_workspace_snapshot() -> None:
    db = Mock()
    db.table.return_value = _query([{"captured_at": "2026-08-06T11:00:00Z"}])

    _enforce_sync_cooldown(
        _context(db),
        "link-1",
        datetime(2026, 8, 6, 12, 5, tzinfo=timezone.utc),
    )


def test_sync_artist_stats_persists_service_owned_snapshots() -> None:
    link_query = _query(
        [{
            "id": "link-1",
            "workspace_id": "workspace-1",
            "soundcharts_uuid": "11e81bd3-4a1f-de5c-8a88-a0369fe50396",
        }]
    )
    db = Mock()
    db.table.return_value = link_query
    service_query = _query([{}])
    service = Mock()
    service.table.return_value = service_query
    client = Mock()
    client.__enter__ = Mock(return_value=client)
    client.__exit__ = Mock(return_value=None)
    client.get_artist_stats.return_value = {
        "streaming": [{"platform": "spotify", "value": 900, "date": "2026-08-06T00:00:00Z"}],
    }

    with (
        patch("app.routers.streaming.SoundchartsClient", return_value=client),
        patch("app.routers.streaming.get_service_client", return_value=service),
    ):
        result = sync_artist_stats("link-1", _context(db))

    assert result["snapshots_written"] == 1
    client.get_artist_stats.assert_called_once_with(
        "11e81bd3-4a1f-de5c-8a88-a0369fe50396",
        period_days=7,
    )
    rows = service_query.upsert.call_args.args[0]
    assert rows[0]["metric_type"] == "streaming"
    assert service_query.upsert.call_args.kwargs["on_conflict"] == (
        "artist_link_id,captured_at,platform,metric_type"
    )


def test_sync_artist_stats_hides_upstream_authorization_details() -> None:
    db = Mock()
    db.table.return_value = _query(
        [{
            "id": "link-1",
            "workspace_id": "workspace-1",
            "soundcharts_uuid": "11e81bd3-4a1f-de5c-8a88-a0369fe50396",
        }]
    )
    request = httpx.Request("GET", "https://customer.api.soundcharts.com/test")
    response = httpx.Response(403, request=request)
    client = Mock()
    client.__enter__ = Mock(return_value=client)
    client.__exit__ = Mock(return_value=None)
    client.get_artist_stats.side_effect = httpx.HTTPStatusError(
        "forbidden",
        request=request,
        response=response,
    )

    with patch("app.routers.streaming.SoundchartsClient", return_value=client):
        with pytest.raises(HTTPException) as exc_info:
            sync_artist_stats("link-1", _context(db))

    assert exc_info.value.status_code == 502
    assert exc_info.value.detail["error"]["code"] == "soundcharts_upstream_error"
    assert exc_info.value.detail["error"]["details"] == {"status": 403}


def test_streaming_summary_returns_latest_metric_per_platform() -> None:
    db = Mock()
    db.table.return_value = _query(
        [
            {"id": "new", "metric_type": "streaming", "platform": "spotify"},
            {"id": "old", "metric_type": "streaming", "platform": "spotify"},
            {"id": "social", "metric_type": "social", "platform": "instagram"},
        ]
    )

    result = get_streaming_summary(_context(db), limit=200)

    assert [row["id"] for row in result] == ["new", "social"]
