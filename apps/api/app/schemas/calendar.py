from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


class CalendarEventCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    type: str = Field(default="content", min_length=1, max_length=30)
    starts_at: datetime
    ends_at: Optional[datetime] = None
    all_day: bool = False
    project_id: Optional[UUID] = None
    notes: Optional[str] = Field(default=None, max_length=10000)

    model_config = {"str_strip_whitespace": True}


class CalendarEventUpdate(BaseModel):
    title: Optional[str] = Field(default=None, min_length=1, max_length=200)
    type: Optional[str] = Field(default=None, min_length=1, max_length=30)
    starts_at: Optional[datetime] = None
    ends_at: Optional[datetime] = None
    all_day: Optional[bool] = None
    project_id: Optional[UUID] = None
    notes: Optional[str] = Field(default=None, max_length=10000)

    model_config = {"str_strip_whitespace": True}
