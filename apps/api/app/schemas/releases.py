from __future__ import annotations

from datetime import date
from typing import Optional
from uuid import UUID

from pydantic import BaseModel


class ReleasePlanCreate(BaseModel):
    release_date: date
    status: str = "draft"


class ReleasePlanUpdate(BaseModel):
    release_date: Optional[date] = None
    status: Optional[str] = None


class MilestoneCreate(BaseModel):
    title: str
    category: str
    due_date: Optional[date] = None
    status: str = "pending"
    position: int = 0


class MilestoneUpdate(BaseModel):
    title: Optional[str] = None
    category: Optional[str] = None
    due_date: Optional[date] = None
    status: Optional[str] = None
    position: Optional[int] = None
