"""Workspaces & teams routes (ARCHITECTURE.md section 3)."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.core.auth import AuthContext, get_auth_context
from app.core.config import get_settings
from app.core.db import get_service_client
from app.core.deps import WorkspaceContext, get_workspace_context, require_writer
from app.schemas.workspaces import MemberInvite, MemberUpdate, WorkspaceCreate, WorkspaceUpdate

router = APIRouter(prefix="/workspaces", tags=["workspaces"])

def _require_super_admin(auth: AuthContext = Depends(get_auth_context)) -> AuthContext:
    if not auth.email or auth.email.lower() not in get_settings().super_admin_email_set:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                            detail={"error": {"code": "forbidden", "message": "super admin only"}})
    return auth


@router.get("")
def list_workspaces(auth: AuthContext = Depends(get_auth_context)) -> list[dict]:
    from app.core.db import get_user_client
    db = get_user_client(auth.token)
    res = db.table("workspace_members").select("role, workspaces(*)").eq("user_id", auth.user_id).execute()
    return res.data or []


@router.post("", status_code=status.HTTP_201_CREATED)
def create_workspace(body: WorkspaceCreate, auth: AuthContext = Depends(get_auth_context)) -> dict:
    svc = get_service_client()
    ws = svc.table("workspaces").insert({**body.model_dump(), "owner_id": auth.user_id}).execute().data[0]
    svc.table("workspace_members").insert({"workspace_id": ws["id"], "user_id": auth.user_id, "role": "owner"}).execute()
    return ws


@router.get("/{workspace_id}")
def get_workspace(ctx: WorkspaceContext = Depends(get_workspace_context)) -> dict:
    row = ctx.db.table("workspaces").select("*").eq("id", ctx.workspace_id).maybe_single().execute()
    return row.data


@router.patch("/{workspace_id}")
def update_workspace(body: WorkspaceUpdate, ctx: WorkspaceContext = Depends(require_writer)) -> dict:
    if ctx.role not in ("owner", "admin"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                            detail={"error": {"code": "forbidden", "message": "owner or admin required"}})
    updates = body.model_dump(exclude_none=True)
    if not updates:
        return get_workspace(ctx)
    res = ctx.db.table("workspaces").update(updates).eq("id", ctx.workspace_id).execute()
    return res.data[0]


@router.get("/{workspace_id}/members")
def list_members(ctx: WorkspaceContext = Depends(get_workspace_context)) -> list[dict]:
    res = ctx.db.table("workspace_members").select("*, profiles(display_name,avatar_url)").eq("workspace_id", ctx.workspace_id).execute()
    return res.data or []


@router.post("/{workspace_id}/members", status_code=status.HTTP_201_CREATED)
def invite_member(body: MemberInvite, ctx: WorkspaceContext = Depends(require_writer)) -> dict:
    if ctx.role not in ("owner", "admin"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                            detail={"error": {"code": "forbidden", "message": "owner or admin required"}})
    svc = get_service_client()
    res = svc.table("workspace_members").insert({"workspace_id": ctx.workspace_id, "user_id": body.user_id, "role": body.role}).execute()
    return res.data[0]


@router.patch("/{workspace_id}/members/{user_id}")
def update_member(user_id: str, body: MemberUpdate, ctx: WorkspaceContext = Depends(require_writer)) -> dict:
    if ctx.role not in ("owner", "admin"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                            detail={"error": {"code": "forbidden", "message": "owner or admin required"}})
    svc = get_service_client()
    res = svc.table("workspace_members").update({"role": body.role}).eq("workspace_id", ctx.workspace_id).eq("user_id", user_id).execute()
    if not res.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail={"error": {"code": "not_found", "message": "member not found"}})
    return res.data[0]


@router.delete("/{workspace_id}/members/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_member(user_id: str, ctx: WorkspaceContext = Depends(require_writer)) -> None:
    if ctx.role not in ("owner", "admin"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                            detail={"error": {"code": "forbidden", "message": "owner or admin required"}})
    svc = get_service_client()
    svc.table("workspace_members").delete().eq("workspace_id", ctx.workspace_id).eq("user_id", user_id).execute()


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
        rows = svc.table("workspaces").select("*, workspace_members(user_id, role)").eq("owner_id", uid).execute().data or []
    else:
        rows = svc.table("workspaces").select("*, workspace_members(user_id, role)").order("created_at", desc=True).execute().data or []
    return rows


@router.patch("/admin/workspaces/{workspace_id}/plan")
def admin_set_plan(
    workspace_id: str,
    plan: str = Query(...),
    auth: AuthContext = Depends(_require_super_admin),
) -> dict:
    """Set a workspace's plan (free/pro/team). Super admin only."""
    if plan not in ("free", "pro", "team"):
        raise HTTPException(status_code=400, detail={"error": {"code": "invalid_plan", "message": "plan must be free, pro, or team"}})
    svc = get_service_client()
    res = svc.table("workspaces").update({"plan": plan}).eq("id", workspace_id).execute()
    if not res.data:
        raise HTTPException(status_code=404, detail={"error": {"code": "not_found", "message": "workspace not found"}})
    return res.data[0]
