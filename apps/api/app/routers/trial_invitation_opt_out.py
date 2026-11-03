"""Public confirmation endpoint for signed promotional invitation opt-outs."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.core.db import get_service_client
from app.integrations.trial_invitation_tokens import (
    InvitationSigningUnavailable,
    verify_opt_out_token,
)

router = APIRouter(prefix="/trial-invitations", tags=["trial-invitations"])


class OptOutRequest(BaseModel):
    token: str = Field(min_length=97, max_length=97)


@router.post("/unsubscribe")
def unsubscribe(request: OptOutRequest) -> dict[str, bool]:
    try:
        delivery_id = verify_opt_out_token(request.token)
    except InvitationSigningUnavailable as exc:
        raise HTTPException(status_code=503, detail="Unsubscribe is temporarily unavailable") from exc
    if delivery_id is None:
        raise HTTPException(status_code=400, detail="This unsubscribe link is invalid")
    try:
        result = get_service_client().rpc(
            "record_trial_invitation_opt_out", {"p_delivery_id": str(delivery_id)}
        ).execute()
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Unsubscribe is temporarily unavailable") from exc
    if result.data is not True:
        raise HTTPException(status_code=400, detail="This unsubscribe link is invalid")
    return {"unsubscribed": True}
