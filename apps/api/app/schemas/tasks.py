from __future__ import annotations

from datetime import date, datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel


class TaskCreate(BaseModel):
    title: str
    project_id: Optional[UUID] = None
    description: Optional[str] = None
    status: str = "todo"
    priority: str = "medium"
    due_date: Optional[date] = None
    assignee_id: Optional[UUID] = None


class TaskUpdate(BaseModel):
    title: Optional[str] = None
    project_id: Optional[UUID] = None
    description: Optional[str] = None
    status: Optional[str] = None
    priority: Optional[str] = None
    due_date: Optional[date] = None
    assignee_id: Optional[UUID] = None
    completed_at: Optional[datetime] = None


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
