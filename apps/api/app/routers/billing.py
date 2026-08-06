"""Billing routes — Stripe checkout, portal, and webhook stubs.

These endpoints return 501 until Stripe keys are configured. Once
STRIPE_SECRET_KEY is set, they create real Stripe sessions.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from app.core.config import get_settings
from app.core.deps import WorkspaceContext, require_writer

router = APIRouter(prefix="/billing", tags=["billing"])


def _require_stripe():
    settings = get_settings()
    if not settings.stripe_secret_key:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail={"error": {"code": "stripe_not_configured", "message": "Stripe is not configured yet"}},
        )
    return settings


@router.post("/checkout")
def create_checkout(
    ctx: WorkspaceContext = Depends(require_writer),
) -> dict:
    """Create a Stripe Checkout session for plan upgrade."""
    _require_stripe()
    # TODO: create stripe.checkout.Session with price lookup
    return {"url": None}


@router.get("/portal")
def billing_portal(
    ctx: WorkspaceContext = Depends(require_writer),
) -> dict:
    """Create a Stripe Billing Portal session for plan management."""
    _require_stripe()
    # TODO: create stripe.billing_portal.Session
    return {"url": None}


@router.post("/webhook")
async def stripe_webhook() -> dict:
    """Receive Stripe webhook events (subscription updates, payments)."""
    # Fail closed until signature verification and event handling are shipped.
    # Configuring a secret alone must never make this endpoint accept events.
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail={
            "error": {
                "code": "stripe_webhook_not_implemented",
                "message": "Stripe webhook processing is not enabled yet",
            }
        },
    )
