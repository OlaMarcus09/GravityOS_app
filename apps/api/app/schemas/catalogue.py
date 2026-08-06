from __future__ import annotations

from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field

MAX_CATALOGUE_FILE_SIZE = 500 * 1024 * 1024


class CatalogueItemCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    kind: str = Field(min_length=1, max_length=50)
    project_id: Optional[UUID] = None
    status: str = Field(default="wip", min_length=1, max_length=30)
    isrc: Optional[str] = Field(default=None, max_length=20)
    bpm: Optional[int] = Field(default=None, ge=0, le=400)
    key: Optional[str] = Field(default=None, max_length=50)
    file_size: Optional[int] = Field(default=None, ge=0, le=MAX_CATALOGUE_FILE_SIZE)
    tags: list[str] = Field(default_factory=list, max_length=50)

    model_config = {"str_strip_whitespace": True}


class CatalogueItemUpdate(BaseModel):
    title: Optional[str] = Field(default=None, min_length=1, max_length=200)
    kind: Optional[str] = Field(default=None, min_length=1, max_length=50)
    project_id: Optional[UUID] = None
    status: Optional[str] = Field(default=None, min_length=1, max_length=30)
    isrc: Optional[str] = Field(default=None, max_length=20)
    bpm: Optional[int] = Field(default=None, ge=0, le=400)
    key: Optional[str] = Field(default=None, max_length=50)
    tags: Optional[list[str]] = Field(default=None, max_length=50)

    model_config = {"str_strip_whitespace": True}
