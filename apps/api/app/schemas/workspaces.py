from __future__ import annotations

from typing import Optional

from pydantic import BaseModel


class WorkspaceCreate(BaseModel):
    name: str
    type: str = "personal"


class WorkspaceUpdate(BaseModel):
    name: Optional[str] = None
    type: Optional[str] = None


class MemberInvite(BaseModel):
    user_id: str
    role: str = "member"


class MemberUpdate(BaseModel):
    role: str
