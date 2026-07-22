"""Catalogue Vault routes (ARCHITECTURE.md section 3).

Uploads use Supabase Storage signed URLs: POST returns a signed upload URL;
GET /{id} returns a signed download URL. Files never stream through the API.
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.core.db import get_service_client
from app.core.deps import (
    PLAN_LIMITS,
    WorkspaceContext,
    enforce_plan_limit,
    get_workspace_context,
    require_writer,
)
from app.schemas.catalogue import CatalogueItemCreate, CatalogueItemUpdate

router = APIRouter(prefix="/catalogue", tags=["catalogue"])

_STORAGE_BUCKET = "catalogue"


def _get_or_404(ctx: WorkspaceContext, item_id: str) -> dict:
    row = ctx.db.table("catalogue_items").select("*").eq("id", item_id).eq("workspace_id", ctx.workspace_id).maybe_single().execute()
    if not row.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail={"error": {"code": "not_found", "message": "catalogue item not found"}})
    return row.data


@router.get("")
def list_catalogue(
    ctx: WorkspaceContext = Depends(get_workspace_context),
    project_id: Optional[str] = Query(None),
    kind: Optional[str] = Query(None),
    status_filter: Optional[str] = Query(None, alias="status"),
) -> list[dict]:
    q = ctx.db.table("catalogue_items").select("*").eq("workspace_id", ctx.workspace_id)
    if project_id:
        q = q.eq("project_id", project_id)
    if kind:
        q = q.eq("kind", kind)
    if status_filter:
        q = q.eq("status", status_filter)
    return q.order("created_at", desc=True).execute().data or []


@router.post("", status_code=status.HTTP_201_CREATED)
def create_catalogue_item(
    body: CatalogueItemCreate,
    ctx: WorkspaceContext = Depends(enforce_plan_limit("catalogue_items")),
) -> dict:
    limit = PLAN_LIMITS.get(ctx.plan, {}).get("catalogue_items")
    if limit is not None:
        count_res = ctx.db.table("catalogue_items").select("id", count="exact").eq("workspace_id", ctx.workspace_id).execute()
        if (count_res.count or 0) >= limit:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"error": {"code": "plan_limit", "message": f"free plan allows {limit} catalogue items"}},
            )
    storage_path = f"{ctx.workspace_id}/{body.title.replace(' ', '_')}"
    svc = get_service_client()
    signed = svc.storage.from_(_STORAGE_BUCKET).create_signed_upload_url(storage_path)
    payload = body.model_dump(exclude_none=True, mode="json")
    payload["storage_path"] = storage_path
    res = ctx.db.table("catalogue_items").insert({**payload, "workspace_id": ctx.workspace_id}).execute()
    return {**res.data[0], "upload_url": signed.get("signedURL") or signed.get("signed_url")}


@router.get("/{item_id}")
def get_catalogue_item(item_id: str, ctx: WorkspaceContext = Depends(get_workspace_context)) -> dict:
    item = _get_or_404(ctx, item_id)
    svc = get_service_client()
    signed = svc.storage.from_(_STORAGE_BUCKET).create_signed_url(item["storage_path"], 3600)
    return {**item, "download_url": signed.get("signedURL") or signed.get("signed_url")}


@router.patch("/{item_id}")
def update_catalogue_item(item_id: str, body: CatalogueItemUpdate, ctx: WorkspaceContext = Depends(require_writer)) -> dict:
    _get_or_404(ctx, item_id)
    updates = body.model_dump(exclude_none=True, mode="json")
    if not updates:
        return _get_or_404(ctx, item_id)
    return ctx.db.table("catalogue_items").update(updates).eq("id", item_id).eq("workspace_id", ctx.workspace_id).execute().data[0]


@router.delete("/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_catalogue_item(item_id: str, ctx: WorkspaceContext = Depends(require_writer)) -> None:
    _get_or_404(ctx, item_id)
    ctx.db.table("catalogue_items").delete().eq("id", item_id).eq("workspace_id", ctx.workspace_id).execute()
