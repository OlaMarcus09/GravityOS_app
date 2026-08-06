from __future__ import annotations

from datetime import datetime, timedelta, timezone
from numbers import Real
from typing import Any

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.core.db import get_service_client
from app.core.deps import WorkspaceContext, get_workspace_context, require_writer
from app.core.rate_limit import check_rate_limit
from app.integrations.soundcharts import SoundchartsClient, SoundchartsNotConfiguredError
from app.schemas.streaming import ArtistStreamingLinkCreate

router = APIRouter(prefix="/streaming", tags=["streaming"])

_STAT_GROUPS = ("social", "streaming", "popularity", "retention", "score")
_SYNC_COOLDOWN = timedelta(minutes=15)


def _enforce_sync_cooldown(ctx: WorkspaceContext, link_id: str, now: datetime) -> None:
    """Avoid repeatedly invoking Soundcharts for the same workspace/link.

    Snapshots are persisted in Supabase, so this guard works across API
    instances (and survives process restarts). It intentionally uses the
    latest captured timestamp rather than an in-memory limiter.
    """
    rows = (
        ctx.db.table("streaming_snapshots")
        .select("captured_at")
        .eq("workspace_id", ctx.workspace_id)
        .eq("artist_link_id", link_id)
        .order("captured_at", desc=True)
        .limit(1)
        .execute()
        .data
        or []
    )
    if not rows:
        return
    raw = rows[0].get("captured_at")
    if not isinstance(raw, str):
        return
    try:
        captured = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        if captured.tzinfo is None:
            captured = captured.replace(tzinfo=timezone.utc)
    except ValueError:
        return
    if now - captured < _SYNC_COOLDOWN:
        retry_after = max(1, int((_SYNC_COOLDOWN - (now - captured)).total_seconds()))
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            headers={"Retry-After": str(retry_after)},
            detail={"error": {"code": "sync_cooldown", "message": "Soundcharts sync is available again shortly"}},
        )


def _link_or_404(ctx: WorkspaceContext, link_id: str) -> dict[str, Any]:
    rows = (
        ctx.db.table("artist_streaming_links")
        .select("*")
        .eq("id", link_id)
        .eq("workspace_id", ctx.workspace_id)
        .limit(1)
        .execute()
        .data
        or []
    )
    if not rows:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "not_found", "message": "Soundcharts artist link not found"}},
        )
    return rows[0]


def _snapshot_rows(
    payload: dict[str, Any],
    *,
    workspace_id: str,
    artist_link_id: str,
    synced_at: datetime,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    fallback_date = synced_at.isoformat()
    for metric_type in _STAT_GROUPS:
        items = payload.get(metric_type)
        if not isinstance(items, list):
            continue
        for item in items:
            if not isinstance(item, dict):
                continue
            platform = item.get("platform")
            value = item.get("value")
            if not isinstance(platform, str) or not platform.strip():
                continue
            if isinstance(value, bool) or not isinstance(value, Real):
                continue
            captured_at = item.get("date") if isinstance(item.get("date"), str) else fallback_date
            rows.append(
                {
                    "workspace_id": workspace_id,
                    "artist_link_id": artist_link_id,
                    "captured_at": captured_at,
                    "platform": platform.strip().lower(),
                    "metric_type": metric_type,
                    "value": value,
                }
            )
    return rows


@router.get("/link")
def get_artist_link(
    ctx: WorkspaceContext = Depends(get_workspace_context),
) -> dict[str, Any] | None:
    rows = (
        ctx.db.table("artist_streaming_links")
        .select("*")
        .eq("workspace_id", ctx.workspace_id)
        .eq("platform", "soundcharts")
        .limit(1)
        .execute()
        .data
        or []
    )
    return rows[0] if rows else None


@router.put("/link")
def connect_artist(
    body: ArtistStreamingLinkCreate,
    ctx: WorkspaceContext = Depends(require_writer),
) -> dict[str, Any]:
    payload = {
        **body.model_dump(mode="json"),
        "workspace_id": ctx.workspace_id,
        "connected_at": datetime.now(timezone.utc).isoformat(),
    }
    result = (
        ctx.db.table("artist_streaming_links")
        .upsert(payload, on_conflict="workspace_id,platform")
        .execute()
    )
    return result.data[0]


@router.delete("/link/{link_id}", status_code=status.HTTP_204_NO_CONTENT)
def disconnect_artist(
    link_id: str,
    ctx: WorkspaceContext = Depends(require_writer),
) -> None:
    _link_or_404(ctx, link_id)
    (
        ctx.db.table("artist_streaming_links")
        .delete()
        .eq("id", link_id)
        .eq("workspace_id", ctx.workspace_id)
        .execute()
    )


@router.get("/summary")
def get_streaming_summary(
    ctx: WorkspaceContext = Depends(get_workspace_context),
    limit: int = Query(default=200, ge=1, le=500),
) -> list[dict[str, Any]]:
    rows = (
        ctx.db.table("streaming_snapshots")
        .select("*")
        .eq("workspace_id", ctx.workspace_id)
        .order("captured_at", desc=True)
        .limit(limit)
        .execute()
        .data
        or []
    )
    latest: dict[tuple[str, str], dict[str, Any]] = {}
    for row in rows:
        key = (row["metric_type"], row["platform"])
        latest.setdefault(key, row)
    return list(latest.values())


@router.post("/link/{link_id}/sync")
def sync_artist_stats(
    link_id: str,
    ctx: WorkspaceContext = Depends(require_writer),
) -> dict[str, Any]:
    link = _link_or_404(ctx, link_id)
    synced_at = datetime.now(timezone.utc)
    check_rate_limit(
        f"soundcharts:sync:{ctx.workspace_id}:{ctx.auth.user_id}",
        limit=4,
        window_seconds=900,
    )
    _enforce_sync_cooldown(ctx, link_id, synced_at)
    try:
        with SoundchartsClient() as client:
            payload = client.get_artist_stats(str(link["soundcharts_uuid"]), period_days=7)
    except SoundchartsNotConfiguredError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"error": {"code": "soundcharts_not_configured", "message": str(exc)}},
        ) from exc
    except httpx.HTTPStatusError as exc:
        upstream_status = exc.response.status_code
        message = "Soundcharts rejected the request" if upstream_status in (401, 403) else "Soundcharts data is temporarily unavailable"
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={
                "error": {
                    "code": "soundcharts_upstream_error",
                    "message": message,
                    "details": {"status": upstream_status},
                }
            },
        ) from exc
    except httpx.HTTPError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={"error": {"code": "soundcharts_unavailable", "message": "Soundcharts data is temporarily unavailable"}},
        ) from exc

    rows = _snapshot_rows(
        payload,
        workspace_id=ctx.workspace_id,
        artist_link_id=link_id,
        synced_at=synced_at,
    )
    if rows:
        (
            get_service_client()
            .table("streaming_snapshots")
            .upsert(
                rows,
                on_conflict="artist_link_id,captured_at,platform,metric_type",
            )
            .execute()
        )
    return {
        "synced_at": synced_at.isoformat(),
        "snapshots_written": len(rows),
    }
