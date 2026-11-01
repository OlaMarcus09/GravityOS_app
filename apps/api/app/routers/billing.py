"""Read workspace trial status. Payment collection is disabled in this release."""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status

from app.core.deps import WorkspaceContext, get_workspace_context
from app.services.entitlements import effective_plan, trial_status

router = APIRouter(prefix="/billing", tags=["billing"])


@router.get("/details")
def billing_details(ctx: WorkspaceContext = Depends(get_workspace_context)) -> dict:
    response = (
        ctx.db.table("workspaces")
        .select("plan,billing_status,current_period_start,current_period_end,trial_started_at,trial_expires_at")
        .eq("id", ctx.workspace_id)
        .maybe_single()
        .execute()
    )
    workspace = response.data if response else None
    if not workspace:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "workspace_not_found", "message": "Workspace not found"}},
        )
    at = datetime.now(timezone.utc)
    return {
        **workspace,
        "plan": effective_plan(workspace, at=at),
        "trial_status": trial_status(workspace, at=at),
        "checkout_eligible": False,
    }


@router.post("/checkout")
@router.get("/portal")
@router.post("/verify")
@router.post("/webhook")
def payments_disabled() -> None:
    """Fail closed without reading credentials, calling a provider, or writing data."""
    raise HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail={
            "error": {
                "code": "billing_checkout_disabled",
                "message": "Paid checkout is not enabled. No payment will be collected.",
            }
        },
    )
