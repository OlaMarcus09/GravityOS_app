"""Workspaces & teams routes (ARCHITECTURE.md section 3)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from app.core.auth import AuthContext, get_auth_context
from app.core.db import get_service_client
from app.core.deps import WorkspaceContext, get_workspace_context, require_writer
from app.schemas.workspaces import MemberInvite, MemberUpdate, WorkspaceCreate, WorkspaceUpdate

router = APIRouter(prefix="/workspaces", tags=["workspaces"])


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
