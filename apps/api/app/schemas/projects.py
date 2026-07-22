from __future__ import annotations

from datetime import date
from typing import Optional
from uuid import UUID

from pydantic import BaseModel


class ProjectCreate(BaseModel):
    title: str
    type: str = "single"
    status: str = "idea"
    cover_url: Optional[str] = None
    target_release_date: Optional[date] = None
    description: Optional[str] = None


class ProjectUpdate(BaseModel):
    title: Optional[str] = None
    type: Optional[str] = None
    status: Optional[str] = None
    cover_url: Optional[str] = None
    target_release_date: Optional[date] = None
    description: Optional[str] = None


class ProjectOut(BaseModel):
    id: UUID
    workspace_id: UUID
    title: str
    type: str
    status: str
    cover_url: Optional[str]
    target_release_date: Optional[date]
    description: Optional[str]
    created_by: Optional[UUID]
