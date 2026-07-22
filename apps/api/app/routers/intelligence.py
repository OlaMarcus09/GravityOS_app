"""Gravity Score + AI outputs routes (ARCHITECTURE.md section 2.10/2.11/3).

Schema-ready, compute/LLM deferred. These endpoints exist so the frontend
contract is real; they return placeholders in the MVP.
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query

from app.core.deps import WorkspaceContext, get_workspace_context

router = APIRouter(tags=["intelligence"])


@router.get("/gravity-score")
def get_gravity_score(ctx: WorkspaceContext = Depends(get_workspace_context)) -> Optional[dict]:
    # Latest snapshot; compute engine is post-MVP (returns placeholder row if present).
    rows = (
        ctx.db.table("gravity_scores").select("*")
        .eq("workspace_id", ctx.workspace_id).order("computed_at", desc=True).limit(1).execute().data or []
    )
    return rows[0] if rows else None


@router.get("/ai/outputs")
def list_ai_outputs(
    ctx: WorkspaceContext = Depends(get_workspace_context),
    kind: Optional[str] = Query(None),
) -> list[dict]:
    # Stored AI outputs; live LLM calls are post-MVP.
    q = ctx.db.table("ai_outputs").select("*").eq("workspace_id", ctx.workspace_id)
    if kind:
        q = q.eq("kind", kind)
    return q.order("generated_at", desc=True).execute().data or []
