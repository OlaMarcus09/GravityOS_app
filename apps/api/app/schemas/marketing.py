from __future__ import annotations

from datetime import date, datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel


class CampaignCreate(BaseModel):
    name: str
    objective: str
    status: str = "planned"
    start_date: date
    end_date: date
    project_id: Optional[UUID] = None


class CampaignUpdate(BaseModel):
    name: Optional[str] = None
    objective: Optional[str] = None
    status: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None


class ContentPieceCreate(BaseModel):
    platform: str
    format: str
    scheduled_at: Optional[datetime] = None
    status: str = "idea"
    caption: Optional[str] = None


class ContentPieceUpdate(BaseModel):
    platform: Optional[str] = None
    format: Optional[str] = None
    scheduled_at: Optional[datetime] = None
    status: Optional[str] = None
    caption: Optional[str] = None
