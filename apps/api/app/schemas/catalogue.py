from __future__ import annotations

from typing import Optional
from uuid import UUID

from pydantic import BaseModel


class CatalogueItemCreate(BaseModel):
    title: str
    kind: str
    project_id: Optional[UUID] = None
    status: str = "wip"
    isrc: Optional[str] = None
    bpm: Optional[int] = None
    key: Optional[str] = None
    file_size: Optional[int] = None
    tags: list[str] = []


class CatalogueItemUpdate(BaseModel):
    title: Optional[str] = None
    kind: Optional[str] = None
    project_id: Optional[UUID] = None
    status: Optional[str] = None
    isrc: Optional[str] = None
    bpm: Optional[int] = None
    key: Optional[str] = None
    tags: Optional[list[str]] = None
