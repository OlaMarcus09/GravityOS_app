from __future__ import annotations

import re
from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator


class WorkspaceCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    type: str = Field(default="personal", min_length=1, max_length=30)

    model_config = {"str_strip_whitespace": True}


class WorkspaceUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=120)
    type: Optional[str] = Field(default=None, min_length=1, max_length=30)

    model_config = {"str_strip_whitespace": True}


class MemberInvite(BaseModel):
    email: str = Field(max_length=320)
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
