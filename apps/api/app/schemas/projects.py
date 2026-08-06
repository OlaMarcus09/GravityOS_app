from __future__ import annotations

from datetime import date
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


class ProjectCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    type: str = Field(default="single", min_length=1, max_length=30)
    status: str = Field(default="idea", min_length=1, max_length=30)
    cover_url: Optional[str] = Field(default=None, max_length=2048)
    target_release_date: Optional[date] = None
    description: Optional[str] = Field(default=None, max_length=10000)

    model_config = {"str_strip_whitespace": True}


class ProjectUpdate(BaseModel):
    title: Optional[str] = Field(default=None, min_length=1, max_length=200)
    type: Optional[str] = Field(default=None, min_length=1, max_length=30)
    status: Optional[str] = Field(default=None, min_length=1, max_length=30)
    cover_url: Optional[str] = Field(default=None, max_length=2048)
    target_release_date: Optional[date] = None
    description: Optional[str] = Field(default=None, max_length=10000)

    model_config = {"str_strip_whitespace": True}


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
