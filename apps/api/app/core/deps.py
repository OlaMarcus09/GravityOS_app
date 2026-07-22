"""Cross-cutting request dependencies (ARCHITECTURE.md section 3).

- workspace guard: resolves the active workspace from the `X-Workspace-Id`
  header, confirms the caller is a member, and attaches their role.
- plan-limit dependency: a factory that fails create operations gated by
  the workspace plan (e.g. Free = 1 active project).

These are deliberately thin in the skeleton phase. The actual limit numbers
live here so feature routers can just declare the dependency later.
"""
from __future__ import annotations

from dataclasses import dataclass

from fastapi import Depends, Header, HTTPException, status
from supabase import Client

from app.core.auth import AuthContext, get_auth_context
from app.core.db import get_user_client

# Plan → limits. Enforced in FastAPI per ARCHITECTURE.md (plan flags, no payments).
PLAN_LIMITS: dict[str, dict[str, int | None]] = {
    "free": {"active_projects": 1, "catalogue_items": 25},
    "pro":  {"active_projects": None, "catalogue_items": None},   # unlimited
    "team": {"active_projects": None, "catalogue_items": None},
}


@dataclass
class WorkspaceContext:
    workspace_id: str
    role: str
    plan: str
    auth: AuthContext
    db: Client  # user-scoped Supabase client (RLS enforced)

    @property
    def is_read_only(self) -> bool:
        return self.role == "viewer"


def get_db(auth: AuthContext = Depends(get_auth_context)) -> Client:
    """User-scoped Supabase client so all queries run under RLS."""
    return get_user_client(auth.token)


def get_workspace_context(
    x_workspace_id: str = Header(..., alias="X-Workspace-Id"),
    auth: AuthContext = Depends(get_auth_context),
    db: Client = Depends(get_db),
) -> WorkspaceContext:
    """Confirm membership and load role + plan for the active workspace."""
    member = (
        db.table("workspace_members")
        .select("role, workspaces(plan)")
        .eq("workspace_id", x_workspace_id)
        .eq("user_id", auth.user_id)
        .maybe_single()
        .execute()
    )
    if not member.data:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error": {"code": "not_a_member", "message": "not a workspace member"}},
        )
    plan = (member.data.get("workspaces") or {}).get("plan", "free")
    return WorkspaceContext(
        workspace_id=x_workspace_id,
        role=member.data["role"],
        plan=plan,
        auth=auth,
        db=db,
    )


def require_writer(ctx: WorkspaceContext = Depends(get_workspace_context)) -> WorkspaceContext:
    """Block viewers from mutating (ARCHITECTURE.md section 3)."""
    if ctx.is_read_only:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error": {"code": "read_only", "message": "viewer role cannot write"}},
        )
    return ctx


def enforce_plan_limit(resource: str):
    """Factory: dependency that enforces a per-plan cap on `resource`.

    Skeleton phase: the count query per feature is wired when that feature's
    CRUD lands. For now this validates the plan/resource pairing exists so the
    contract is real and importable by routers.
    """

    def _dep(ctx: WorkspaceContext = Depends(require_writer)) -> WorkspaceContext:
        limits = PLAN_LIMITS.get(ctx.plan, {})
        if resource not in limits:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={"error": {"code": "unknown_limit", "message": resource}},
            )
        # Per-feature count check is added alongside each feature's create route.
        return ctx

    return _dep
