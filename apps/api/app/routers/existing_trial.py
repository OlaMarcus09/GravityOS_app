"""Owner-only existing-user trial eligibility and activation."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.core.db import get_service_client
from app.core.deps import WorkspaceContext, get_workspace_context

router = APIRouter(prefix="/billing/existing-trial", tags=["billing"])

_MESSAGES = {
    "already_claimed": "This account has already received a seven-day trial.",
    "email_confirmation_required": "Confirm your email before claiming your trial.",
    "paid_workspace_conflict": "This offer is for owners without a paid or manual plan.",
    "not_owner": "Only the workspace owner can claim this offer.",
    "not_eligible": "This workspace is not eligible for this offer.",
    "window_closed": "The existing-user trial offer is not currently open.",
}


def _owner_context(ctx: WorkspaceContext) -> None:
    if ctx.role != "owner":
        raise HTTPException(403, detail={"error": {
            "code": "not_owner", "message": _MESSAGES["not_owner"],
        }})


def _rpc(name: str, ctx: WorkspaceContext) -> dict:
    result = get_service_client().rpc(name, {
        "p_owner_id": ctx.auth.user_id,
        "p_workspace_id": ctx.workspace_id,
    }).execute()
    return result.data or {}


@router.get("/eligibility")
def existing_trial_eligibility(ctx: WorkspaceContext = Depends(get_workspace_context)) -> dict:
    _owner_context(ctx)
    result = _rpc("existing_user_trial_eligibility", ctx)
    reason = result.get("reason", "not_eligible")
    return {"eligible": reason == "eligible", "reason": reason,
            "message": _MESSAGES.get(reason)}


@router.post("/claim")
def claim_existing_trial(ctx: WorkspaceContext = Depends(get_workspace_context)) -> dict:
    _owner_context(ctx)
    result = _rpc("claim_existing_user_trial", ctx)
    reason = result.get("reason")
    if reason != "activated":
        code = 409 if reason == "already_claimed" else 403 if reason == "not_owner" else 422
        raise HTTPException(code, detail={"error": {
            "code": reason or "not_eligible",
            "message": _MESSAGES.get(reason, _MESSAGES["not_eligible"]),
        }})
    return result
