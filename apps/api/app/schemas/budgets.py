from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Optional
from uuid import UUID

from pydantic import BaseModel


class BudgetCreate(BaseModel):
    name: str
    total_amount: Decimal
    currency: str = "USD"
    project_id: Optional[UUID] = None


class BudgetUpdate(BaseModel):
    name: Optional[str] = None
    total_amount: Optional[Decimal] = None
    currency: Optional[str] = None


class BudgetItemCreate(BaseModel):
    category: str
    label: str
    planned_amount: Decimal
    actual_amount: Optional[Decimal] = None
    spent_at: Optional[date] = None


class BudgetItemUpdate(BaseModel):
    category: Optional[str] = None
    label: Optional[str] = None
    planned_amount: Optional[Decimal] = None
    actual_amount: Optional[Decimal] = None
    spent_at: Optional[date] = None
