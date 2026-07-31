from __future__ import annotations

import re
from typing import Literal, Optional

from pydantic import BaseModel, field_validator


class WorkspaceCreate(BaseModel):
    name: str
    type: str = "personal"


class WorkspaceUpdate(BaseModel):
    name: Optional[str] = None
    type: Optional[str] = None


class MemberInvite(BaseModel):
    email: str
    role: Literal["admin", "member", "viewer"] = "member"

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        normalized = value.strip().lower()
        if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", normalized):
            raise ValueError("enter a valid email address")
        return normalized


class MemberUpdate(BaseModel):
    role: Literal["admin", "member", "viewer"]
