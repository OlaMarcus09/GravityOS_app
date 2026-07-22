"""Budget planner routes (ARCHITECTURE.md section 3)."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.core.deps import WorkspaceContext, get_workspace_context, require_writer
from app.schemas.budgets import BudgetCreate, BudgetItemCreate, BudgetItemUpdate, BudgetUpdate

router = APIRouter(tags=["budgets"])


def _get_budget_or_404(ctx: WorkspaceContext, budget_id: str) -> dict:
    row = ctx.db.table("budgets").select("*").eq("id", budget_id).eq("workspace_id", ctx.workspace_id).maybe_single().execute()
    if not row.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail={"error": {"code": "not_found", "message": "budget not found"}})
    return row.data


def _get_item_or_404(ctx: WorkspaceContext, item_id: str) -> dict:
    row = (
        ctx.db.table("budget_items")
        .select("*, budgets!inner(workspace_id)")
        .eq("id", item_id)
        .eq("budgets.workspace_id", ctx.workspace_id)
        .maybe_single()
        .execute()
    )
    if not row.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail={"error": {"code": "not_found", "message": "budget item not found"}})
    return row.data


@router.get("/budgets")
def list_budgets(
    ctx: WorkspaceContext = Depends(get_workspace_context),
    project_id: Optional[str] = Query(None),
) -> list[dict]:
    q = ctx.db.table("budgets").select("*").eq("workspace_id", ctx.workspace_id)
    if project_id:
        q = q.eq("project_id", project_id)
    return q.order("created_at", desc=True).execute().data or []


@router.post("/budgets", status_code=status.HTTP_201_CREATED)
def create_budget(body: BudgetCreate, ctx: WorkspaceContext = Depends(require_writer)) -> dict:
    res = ctx.db.table("budgets").insert({**body.model_dump(exclude_none=True, mode="json"), "workspace_id": ctx.workspace_id}).execute()
    return res.data[0]


@router.patch("/budgets/{budget_id}")
def update_budget(budget_id: str, body: BudgetUpdate, ctx: WorkspaceContext = Depends(require_writer)) -> dict:
    _get_budget_or_404(ctx, budget_id)
    updates = body.model_dump(exclude_none=True, mode="json")
    if not updates:
        return _get_budget_or_404(ctx, budget_id)
    return ctx.db.table("budgets").update(updates).eq("id", budget_id).eq("workspace_id", ctx.workspace_id).execute().data[0]


@router.post("/budgets/{budget_id}/items", status_code=status.HTTP_201_CREATED)
def add_budget_item(budget_id: str, body: BudgetItemCreate, ctx: WorkspaceContext = Depends(require_writer)) -> dict:
    _get_budget_or_404(ctx, budget_id)
    res = ctx.db.table("budget_items").insert({**body.model_dump(exclude_none=True, mode="json"), "budget_id": budget_id}).execute()
    return res.data[0]


@router.patch("/budget-items/{item_id}")
def update_budget_item(item_id: str, body: BudgetItemUpdate, ctx: WorkspaceContext = Depends(require_writer)) -> dict:
    _get_item_or_404(ctx, item_id)
    updates = body.model_dump(exclude_none=True, mode="json")
    if not updates:
        return _get_item_or_404(ctx, item_id)
    return ctx.db.table("budget_items").update(updates).eq("id", item_id).execute().data[0]


@router.delete("/budget-items/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_budget_item(item_id: str, ctx: WorkspaceContext = Depends(require_writer)) -> None:
    _get_item_or_404(ctx, item_id)
    ctx.db.table("budget_items").delete().eq("id", item_id).execute()
