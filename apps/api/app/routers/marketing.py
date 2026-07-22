"""Marketing planner routes (ARCHITECTURE.md section 3)."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.core.deps import WorkspaceContext, get_workspace_context, require_writer
from app.schemas.marketing import CampaignCreate, CampaignUpdate, ContentPieceCreate, ContentPieceUpdate

router = APIRouter(tags=["marketing"])


def _get_campaign_or_404(ctx: WorkspaceContext, campaign_id: str) -> dict:
    row = ctx.db.table("campaigns").select("*").eq("id", campaign_id).eq("workspace_id", ctx.workspace_id).maybe_single().execute()
    if not row.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail={"error": {"code": "not_found", "message": "campaign not found"}})
    return row.data


def _get_content_or_404(ctx: WorkspaceContext, content_id: str) -> dict:
    row = ctx.db.table("content_pieces").select("*").eq("id", content_id).eq("workspace_id", ctx.workspace_id).maybe_single().execute()
    if not row.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail={"error": {"code": "not_found", "message": "content piece not found"}})
    return row.data


@router.get("/campaigns")
def list_campaigns(
    ctx: WorkspaceContext = Depends(get_workspace_context),
    project_id: Optional[str] = Query(None),
    status_filter: Optional[str] = Query(None, alias="status"),
) -> list[dict]:
    q = ctx.db.table("campaigns").select("*").eq("workspace_id", ctx.workspace_id)
    if project_id:
        q = q.eq("project_id", project_id)
    if status_filter:
        q = q.eq("status", status_filter)
    return q.order("created_at", desc=True).execute().data or []


@router.post("/campaigns", status_code=status.HTTP_201_CREATED)
def create_campaign(body: CampaignCreate, ctx: WorkspaceContext = Depends(require_writer)) -> dict:
    res = ctx.db.table("campaigns").insert({**body.model_dump(exclude_none=True, mode="json"), "workspace_id": ctx.workspace_id}).execute()
    return res.data[0]


@router.patch("/campaigns/{campaign_id}")
def update_campaign(campaign_id: str, body: CampaignUpdate, ctx: WorkspaceContext = Depends(require_writer)) -> dict:
    _get_campaign_or_404(ctx, campaign_id)
    updates = body.model_dump(exclude_none=True, mode="json")
    if not updates:
        return _get_campaign_or_404(ctx, campaign_id)
    return ctx.db.table("campaigns").update(updates).eq("id", campaign_id).eq("workspace_id", ctx.workspace_id).execute().data[0]


@router.post("/campaigns/{campaign_id}/content", status_code=status.HTTP_201_CREATED)
def add_content(campaign_id: str, body: ContentPieceCreate, ctx: WorkspaceContext = Depends(require_writer)) -> dict:
    _get_campaign_or_404(ctx, campaign_id)
    res = ctx.db.table("content_pieces").insert({
        **body.model_dump(exclude_none=True, mode="json"),
        "campaign_id": campaign_id,
        "workspace_id": ctx.workspace_id,
    }).execute()
    return res.data[0]


@router.patch("/content/{content_id}")
def update_content(content_id: str, body: ContentPieceUpdate, ctx: WorkspaceContext = Depends(require_writer)) -> dict:
    _get_content_or_404(ctx, content_id)
    updates = body.model_dump(exclude_none=True, mode="json")
    if not updates:
        return _get_content_or_404(ctx, content_id)
    return ctx.db.table("content_pieces").update(updates).eq("id", content_id).eq("workspace_id", ctx.workspace_id).execute().data[0]


@router.delete("/content/{content_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_content(content_id: str, ctx: WorkspaceContext = Depends(require_writer)) -> None:
    _get_content_or_404(ctx, content_id)
    ctx.db.table("content_pieces").delete().eq("id", content_id).eq("workspace_id", ctx.workspace_id).execute()
