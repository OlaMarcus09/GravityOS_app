"""Workspaces & teams routes (ARCHITECTURE.md section 3)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.core.auth import AuthContext, get_auth_context
from app.core.config import get_settings
from app.core.db import get_service_client
from app.core.deps import WorkspaceContext, get_db, get_workspace_context, require_writer
from app.core.rate_limit import check_rate_limit
from app.schemas.workspaces import MemberInvite, MemberUpdate, WorkspaceCreate, WorkspaceUpdate

router = APIRouter(prefix="/workspaces", tags=["workspaces"])

INVITATION_TTL_DAYS = 7


def _require_team_admin(ctx: WorkspaceContext) -> None:
    if ctx.role not in ("owner", "admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error": {"code": "forbidden", "message": "owner or admin required"}},
        )
    if ctx.plan != "team":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": {
                    "code": "plan_required",
                    "message": "Team invitations require the Team plan",
                }
            },
        )


def _invitation_expiry() -> str:
    return (datetime.now(timezone.utc) + timedelta(days=INVITATION_TTL_DAYS)).isoformat()


def _send_invitation_email(email: str) -> bool:
    """Use Supabase's configured Auth mailer; existing users still see in-app invites."""
    try:
        get_service_client().auth.admin.invite_user_by_email(
            email,
            {"redirect_to": f"{get_settings().web_app_url.rstrip('/')}/auth/invite"},
        )
        return True
    except Exception:
        return False


def _notify(
    *,
    workspace_id: str,
    kind: str,
    title: str,
    message: str,
    recipient_id: str | None = None,
    recipient_email: str | None = None,
    action_url: str | None = None,
    metadata: dict | None = None,
) -> None:
    payload = {
        "workspace_id": workspace_id,
        "recipient_id": recipient_id,
        "recipient_email": recipient_email.strip().lower() if recipient_email else None,
        "kind": kind,
        "title": title,
        "message": message,
        "action_url": action_url,
        "metadata": metadata or {},
    }
    try:
        get_service_client().table("notifications").insert(payload).execute()
    except Exception:
        # Notification delivery must not roll back the primary workspace action.
        return


def _get_managed_member(user_id: str, ctx: WorkspaceContext, svc) -> dict:
    response = (
        svc.table("workspace_members")
        .select("id,user_id,role")
        .eq("workspace_id", ctx.workspace_id)
        .eq("user_id", user_id)
        .maybe_single()
        .execute()
    )
    member = response.data if response else None
    if not member:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "not_found", "message": "member not found"}},
        )
    return member


def _authorize_member_management(member: dict, ctx: WorkspaceContext) -> None:
    if member["role"] == "owner":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "error": {
                    "code": "owner_protected",
                    "message": "The workspace owner's membership cannot be changed or removed",
                }
            },
        )
    if member["user_id"] == ctx.auth.user_id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "error": {
                    "code": "self_management_forbidden",
                    "message": "You cannot change or remove your own membership",
                }
            },
        )
    if ctx.role == "admin" and member["role"] == "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": {
                    "code": "owner_required",
                    "message": "Only the workspace owner can manage administrators",
                }
            },
        )


def _require_super_admin(auth: AuthContext = Depends(get_auth_context)) -> AuthContext:
    if not auth.email or auth.email.lower() not in get_settings().super_admin_email_set:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error": {"code": "forbidden", "message": "super admin only"}},
        )
    return auth


@router.get("")
def list_workspaces(auth: AuthContext = Depends(get_auth_context)) -> list[dict]:
    from app.core.db import get_user_client

    db = get_user_client(auth.token)
    res = (
        db.table("workspace_members")
        .select("role, workspaces(*)")
        .eq("user_id", auth.user_id)
        .execute()
    )
    return res.data or []


@router.post("", status_code=status.HTTP_201_CREATED)
def create_workspace(body: WorkspaceCreate, auth: AuthContext = Depends(get_auth_context)) -> dict:
    svc = get_service_client()
    ws = (
        svc.table("workspaces")
        .insert({**body.model_dump(), "owner_id": auth.user_id})
        .execute()
        .data[0]
    )
    svc.table("workspace_members").insert(
        {"workspace_id": ws["id"], "user_id": auth.user_id, "role": "owner"}
    ).execute()
    return ws


@router.get("/invitations/pending")
def list_my_pending_invitations(auth: AuthContext = Depends(get_auth_context)) -> list[dict]:
    if not auth.email:
        return []
    svc = get_service_client()
    now = datetime.now(timezone.utc).isoformat()
    res = (
        svc.table("workspace_invitations")
        .select("*, workspaces(name)")
        .eq("email", auth.email.strip().lower())
        .is_("accepted_at", "null")
        .is_("revoked_at", "null")
        .gt("expires_at", now)
        .order("invited_at", desc=True)
        .execute()
    )
    return res.data or []


@router.post("/invitations/{invitation_id}/accept")
def accept_invitation(
    invitation_id: str,
    auth: AuthContext = Depends(get_auth_context),
    db=Depends(get_db),
) -> dict:
    if not auth.email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": {"code": "email_required", "message": "Your account has no email address"}
            },
        )
    try:
        rows = (
            db.rpc("accept_workspace_invitation", {"invitation_id": invitation_id}).execute().data
            or []
        )
    except Exception as exc:
        message = str(exc).lower()
        if "expired" in message:
            code, http_status = "invite_expired", status.HTTP_410_GONE
        elif "no longer available" in message:
            code, http_status = "invite_unavailable", status.HTTP_409_CONFLICT
        else:
            code, http_status = "not_found", status.HTTP_404_NOT_FOUND
        raise HTTPException(
            status_code=http_status,
            detail={"error": {"code": code, "message": str(exc)}},
        ) from exc
    if not rows:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "not_found", "message": "invitation not found"}},
        )
    return {"membership_id": rows[0]["membership_id"], "workspace_id": rows[0]["workspace_id"]}


@router.get("/{workspace_id}")
def get_workspace(ctx: WorkspaceContext = Depends(get_workspace_context)) -> dict:
    row = ctx.db.table("workspaces").select("*").eq("id", ctx.workspace_id).maybe_single().execute()
    return row.data


@router.patch("/{workspace_id}")
def update_workspace(
    body: WorkspaceUpdate, ctx: WorkspaceContext = Depends(require_writer)
) -> dict:
    if ctx.role not in ("owner", "admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error": {"code": "forbidden", "message": "owner or admin required"}},
        )
    updates = body.model_dump(exclude_none=True)
    if not updates:
        return get_workspace(ctx)
    res = ctx.db.table("workspaces").update(updates).eq("id", ctx.workspace_id).execute()
    return res.data[0]


@router.get("/{workspace_id}/members")
def list_members(ctx: WorkspaceContext = Depends(get_workspace_context)) -> list[dict]:
    rows = (
        ctx.db.table("workspace_members")
        .select("*")
        .eq("workspace_id", ctx.workspace_id)
        .execute()
        .data
        or []
    )
    user_ids = [row["user_id"] for row in rows]
    profiles = {}
    if user_ids:
        data = (
            get_service_client()
            .table("profiles")
            .select("id,display_name,avatar_url")
            .in_("id", user_ids)
            .execute()
            .data
            or []
        )
        profiles = {profile["id"]: profile for profile in data}
    for row in rows:
        profile = profiles.get(row["user_id"], {})
        row["profiles"] = {
            "display_name": profile.get("display_name"),
            "avatar_url": profile.get("avatar_url"),
        }
    return rows


@router.post("/{workspace_id}/members", status_code=status.HTTP_410_GONE)
def invite_member(body: MemberInvite, ctx: WorkspaceContext = Depends(require_writer)) -> dict:
    """Retained as a clear compatibility error for older web deployments."""
    _require_team_admin(ctx)
    raise HTTPException(
        status_code=status.HTTP_410_GONE,
        detail={
            "error": {
                "code": "invite_endpoint_moved",
                "message": "Use the workspace invitations endpoint",
            }
        },
    )


@router.get("/{workspace_id}/invitations")
def list_workspace_invitations(
    ctx: WorkspaceContext = Depends(get_workspace_context),
) -> list[dict]:
    _require_team_admin(ctx)
    res = (
        get_service_client()
        .table("workspace_invitations")
        .select("*")
        .eq("workspace_id", ctx.workspace_id)
        .order("invited_at", desc=True)
        .execute()
    )
    return res.data or []


@router.post("/{workspace_id}/invitations", status_code=status.HTTP_201_CREATED)
def create_invitation(body: MemberInvite, ctx: WorkspaceContext = Depends(require_writer)) -> dict:
    _require_team_admin(ctx)
    if body.role == "admin" and ctx.role != "owner":
        raise HTTPException(status_code=403, detail={"error": {"code": "owner_required", "message": "Only the workspace owner can invite administrators"}})
    check_rate_limit(f"invite:create:{ctx.workspace_id}:{ctx.auth.user_id}", limit=10)
    if body.email == (ctx.auth.email or "").strip().lower():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "error": {
                    "code": "already_a_member",
                    "message": "You are already a workspace member",
                }
            },
        )
    svc = get_service_client()
    current_response = (
        svc.table("workspace_invitations")
        .select("id,accepted_at")
        .eq("workspace_id", ctx.workspace_id)
        .eq("email", body.email)
        .maybe_single()
        .execute()
    )
    current = current_response.data if current_response else None
    payload = {
        "role": body.role,
        "invited_by": ctx.auth.user_id,
        "invited_at": datetime.now(timezone.utc).isoformat(),
        "expires_at": _invitation_expiry(),
        "accepted_at": None,
        "revoked_at": None,
    }
    if current:
        if current.get("accepted_at"):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "error": {
                        "code": "already_accepted",
                        "message": "This invitation was already accepted",
                    }
                },
            )
        res = svc.table("workspace_invitations").update(payload).eq("id", current["id"]).execute()
    else:
        res = (
            svc.table("workspace_invitations")
            .insert(
                {
                    **payload,
                    "workspace_id": ctx.workspace_id,
                    "email": body.email,
                }
            )
            .execute()
        )
    invitation = res.data[0]
    invitation["email_sent"] = _send_invitation_email(invitation["email"])
    _notify(
        workspace_id=ctx.workspace_id,
        recipient_email=invitation["email"],
        kind="workspace_invitation",
        title="Workspace invitation",
        message="You have been invited to join a Gravity OS workspace.",
        action_url="/auth/invite",
        metadata={"invitation_id": invitation["id"], "role": invitation["role"]},
    )
    return invitation


@router.post("/{workspace_id}/invitations/{invitation_id}/resend")
def resend_invitation(invitation_id: str, ctx: WorkspaceContext = Depends(require_writer)) -> dict:
    _require_team_admin(ctx)
    check_rate_limit(f"invite:resend:{ctx.workspace_id}:{ctx.auth.user_id}", limit=10)
    res = (
        get_service_client()
        .table("workspace_invitations")
        .update(
            {
                "invited_at": datetime.now(timezone.utc).isoformat(),
                "expires_at": _invitation_expiry(),
                "revoked_at": None,
            }
        )
        .eq("id", invitation_id)
        .eq("workspace_id", ctx.workspace_id)
        .is_("accepted_at", "null")
        .execute()
    )
    if not res.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "not_found", "message": "pending invitation not found"}},
        )
    invitation = res.data[0]
    invitation["email_sent"] = _send_invitation_email(invitation["email"])
    _notify(
        workspace_id=ctx.workspace_id,
        recipient_email=invitation["email"],
        kind="workspace_invitation_resent",
        title="Workspace invitation resent",
        message="Your Gravity OS workspace invitation has been renewed.",
        action_url="/auth/invite",
        metadata={"invitation_id": invitation["id"], "role": invitation["role"]},
    )
    return invitation


@router.delete(
    "/{workspace_id}/invitations/{invitation_id}", status_code=status.HTTP_204_NO_CONTENT
)
def revoke_invitation(invitation_id: str, ctx: WorkspaceContext = Depends(require_writer)) -> None:
    _require_team_admin(ctx)
    get_service_client().table("workspace_invitations").update(
        {
            "revoked_at": datetime.now(timezone.utc).isoformat(),
        }
    ).eq("id", invitation_id).eq("workspace_id", ctx.workspace_id).is_(
        "accepted_at", "null"
    ).execute()


@router.patch("/{workspace_id}/members/{user_id}")
def update_member(
    user_id: str, body: MemberUpdate, ctx: WorkspaceContext = Depends(require_writer)
) -> dict:
    if ctx.role not in ("owner", "admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error": {"code": "forbidden", "message": "owner or admin required"}},
        )
    svc = get_service_client()
    member = _get_managed_member(user_id, ctx, svc)
    _authorize_member_management(member, ctx)
    res = (
        svc.table("workspace_members")
        .update({"role": body.role})
        .eq("workspace_id", ctx.workspace_id)
        .eq("user_id", user_id)
        .execute()
    )
    if not res.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "not_found", "message": "member not found"}},
        )
    _notify(
        workspace_id=ctx.workspace_id,
        recipient_id=user_id,
        kind="role_changed",
        title="Your workspace role changed",
        message=f"Your role is now {body.role}.",
        action_url="/team",
        metadata={"role": body.role},
    )
    return res.data[0]


@router.delete("/{workspace_id}/members/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_member(user_id: str, ctx: WorkspaceContext = Depends(require_writer)) -> None:
    if ctx.role not in ("owner", "admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error": {"code": "forbidden", "message": "owner or admin required"}},
        )
    svc = get_service_client()
    member = _get_managed_member(user_id, ctx, svc)
    _authorize_member_management(member, ctx)
    res = (
        svc.table("workspace_members")
        .delete()
        .eq("workspace_id", ctx.workspace_id)
        .eq("user_id", user_id)
        .execute()
    )
    if not res.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "not_found", "message": "member not found"}},
        )


# --- Admin-only routes (super admin) ----------------------------------------


@router.get("/admin/workspaces")
def admin_list_all(
    auth: AuthContext = Depends(_require_super_admin),
    email: Optional[str] = Query(None),
) -> list[dict]:
    """List all workspaces (optionally filtered by owner email)."""
    svc = get_service_client()
    if email:
        # Look up user by email in auth.users via profiles
        user_res = svc.auth.admin.list_users()
        matched = [u for u in user_res if u.email and u.email.lower() == email.lower()]
        if not matched:
            return []
        uid = matched[0].id
        rows = (
            svc.table("workspaces")
            .select("*, workspace_members(user_id, role)")
            .eq("owner_id", uid)
            .execute()
            .data
            or []
        )
    else:
        rows = (
            svc.table("workspaces")
            .select("*, workspace_members(user_id, role)")
            .order("created_at", desc=True)
            .execute()
            .data
            or []
        )
    return rows


@router.patch("/admin/workspaces/{workspace_id}/plan")
def admin_set_plan(
    workspace_id: str,
    plan: str = Query(...),
    auth: AuthContext = Depends(_require_super_admin),
) -> dict:
    """Set a workspace's plan (free/pro/team). Super admin only."""
    if plan not in ("free", "pro", "team"):
        raise HTTPException(
            status_code=400,
            detail={
                "error": {"code": "invalid_plan", "message": "plan must be free, pro, or team"}
            },
        )
    svc = get_service_client()
    existing = svc.table("workspaces").select("id").eq("id", workspace_id).maybe_single().execute()
    if not existing.data:
        raise HTTPException(
            status_code=404,
            detail={"error": {"code": "not_found", "message": "workspace not found"}},
        )
    res = svc.rpc(
        "admin_set_workspace_plan",
        {
            "p_workspace_id": workspace_id,
            "p_new_plan": plan,
            "p_actor_id": auth.user_id,
            "p_actor_email": auth.email,
        },
    ).execute()
    return res.data[0] if isinstance(res.data, list) else res.data


@router.get("/admin/plan-audit")
def admin_plan_audit(
    auth: AuthContext = Depends(_require_super_admin),
    limit: int = Query(50, ge=1, le=200),
) -> list[dict]:
    """Return the newest immutable manual plan-change events."""
    res = (
        get_service_client()
        .table("admin_plan_audit_events")
        .select("*, workspaces(name)")
        .order("created_at", desc=True)
        .limit(limit)
        .execute()
    )
    return res.data or []


@router.get("/admin/users")
def admin_list_users(
    auth: AuthContext = Depends(_require_super_admin),
    email: Optional[str] = Query(None),
) -> list[dict]:
    """List Auth users for support and account-status administration."""
    users = get_service_client().auth.admin.list_users()
    needle = email.strip().lower() if email else ""
    result = []
    for user in users:
        user_email = (user.email or "").lower()
        if needle and needle not in user_email:
            continue
        result.append({
            "id": user.id,
            "email": user.email,
            "created_at": user.created_at,
            "last_sign_in_at": user.last_sign_in_at,
            "banned_until": user.banned_until,
        })
    return result


@router.patch("/admin/users/{user_id}/status")
def admin_set_user_status(
    user_id: str,
    action: str = Query(...),
    auth: AuthContext = Depends(_require_super_admin),
) -> dict:
    """Suspend or reactivate an Auth account and record the support action."""
    if action not in ("suspend", "reactivate"):
        raise HTTPException(status_code=400, detail={"error": {"code": "invalid_action", "message": "action must be suspend or reactivate"}})
    if user_id == auth.user_id:
        raise HTTPException(status_code=409, detail={"error": {"code": "self_action_forbidden", "message": "You cannot suspend your own account"}})
    svc = get_service_client()
    user = svc.auth.admin.get_user_by_id(user_id).user
    if not user:
        raise HTTPException(status_code=404, detail={"error": {"code": "not_found", "message": "user not found"}})
    attributes = {"ban_duration": "none" if action == "reactivate" else "876000h"}
    updated = svc.auth.admin.update_user_by_id(user_id, attributes).user
    svc.table("admin_account_audit_events").insert({
        "user_id": user_id,
        "user_email": user.email or "",
        "actor_id": auth.user_id,
        "actor_email": auth.email or "",
        "action": action,
    }).execute()
    return {
        "id": updated.id,
        "email": updated.email,
        "created_at": updated.created_at,
        "last_sign_in_at": updated.last_sign_in_at,
        "banned_until": updated.banned_until,
    }
