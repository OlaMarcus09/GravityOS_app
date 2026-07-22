from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel


class CalendarEventCreate(BaseModel):
    title: str
    type: str = "content"
    starts_at: datetime
    ends_at: Optional[datetime] = None
    all_day: bool = False
    project_id: Optional[UUID] = None
    notes: Optional[str] = None


class CalendarEventUpdate(BaseModel):
    title: Optional[str] = None
    type: Optional[str] = None
    starts_at: Optional[datetime] = None
    ends_at: Optional[datetime] = None
    all_day: Optional[bool] = None
    project_id: Optional[UUID] = None
    notes: Optional[str] = None
