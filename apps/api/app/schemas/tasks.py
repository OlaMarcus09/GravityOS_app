from __future__ import annotations

from datetime import date, datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


class TaskCreate(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    project_id: Optional[UUID] = None
    description: Optional[str] = Field(default=None, max_length=10000)
    status: str = Field(default="todo", min_length=1, max_length=30)
    priority: str = Field(default="medium", min_length=1, max_length=20)
    due_date: Optional[date] = None
    assignee_id: Optional[UUID] = None

    model_config = {"str_strip_whitespace": True}


class TaskUpdate(BaseModel):
    title: Optional[str] = Field(default=None, min_length=1, max_length=300)
    project_id: Optional[UUID] = None
    description: Optional[str] = Field(default=None, max_length=10000)
    status: Optional[str] = Field(default=None, min_length=1, max_length=30)
    priority: Optional[str] = Field(default=None, min_length=1, max_length=20)
    due_date: Optional[date] = None
    assignee_id: Optional[UUID] = None
    completed_at: Optional[datetime] = None

    model_config = {"str_strip_whitespace": True}


class TaskOut(BaseModel):
    id: UUID
    workspace_id: UUID
    project_id: Optional[UUID]
    title: str
    description: Optional[str]
    status: str
    priority: str
    due_date: Optional[date]
    assignee_id: Optional[UUID]
    created_by: Optional[UUID]
    completed_at: Optional[datetime]
    approval_status: str = "not_required"
    approval_submitted_by: Optional[UUID] = None
    approval_reviewed_by: Optional[UUID] = None
    approval_reviewed_at: Optional[datetime] = None
    approval_note: Optional[str] = None
