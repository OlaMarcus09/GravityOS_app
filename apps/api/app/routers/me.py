"""GET/PATCH /me — profile + memberships (ARCHITECTURE.md section 3).

This is the one route wired end-to-end for the skeleton: verified JWT →
user-scoped Supabase client → Postgres (RLS) → response. Confirms auth and
DB connectivity round-trip before feature CRUD is built.
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from supabase import Client

from app.core.auth import AuthContext, get_auth_context
from app.core.deps import get_db

router = APIRouter(tags=["me"])


class ProfileUpdate(BaseModel):
    display_name: Optional[str] = None
    creative_role: Optional[str] = None
    timezone: Optional[str] = None
    avatar_url: Optional[str] = None


def _read_me(auth: AuthContext, db: Client) -> dict:
    profile = (
        db.table("profiles")
        .select("id, display_name, avatar_url, creative_role, timezone")
        .eq("id", auth.user_id)
        .maybe_single()
        .execute()
    )
    memberships = (
        db.table("workspace_members")
        .select("workspace_id, role, workspaces(name, plan, type)")
        .eq("user_id", auth.user_id)
        .execute()
    )
    return {
        "user_id": auth.user_id,
        "email": auth.email,
        "profile": profile.data,
        "memberships": memberships.data or [],
    }


@router.get("/me")
def read_me(
    auth: AuthContext = Depends(get_auth_context),
    db: Client = Depends(get_db),
) -> dict:
    return _read_me(auth, db)


@router.patch("/me")
def update_me(
    body: ProfileUpdate,
    auth: AuthContext = Depends(get_auth_context),
    db: Client = Depends(get_db),
) -> dict:
    updates = body.model_dump(exclude_none=True)
    if updates:
        db.table("profiles").update(updates).eq("id", auth.user_id).execute()
    return _read_me(auth, db)
