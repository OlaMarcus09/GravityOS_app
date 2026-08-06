from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


class BudgetCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    total_amount: Decimal = Field(ge=0, le=1_000_000_000)
    currency: str = Field(default="USD", min_length=3, max_length=3)
    project_id: Optional[UUID] = None

    model_config = {"str_strip_whitespace": True}


class BudgetUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=200)
    total_amount: Optional[Decimal] = Field(default=None, ge=0, le=1_000_000_000)
    currency: Optional[str] = Field(default=None, min_length=3, max_length=3)

    model_config = {"str_strip_whitespace": True}


class BudgetItemCreate(BaseModel):
    category: str = Field(min_length=1, max_length=100)
    label: str = Field(min_length=1, max_length=200)
    planned_amount: Decimal = Field(ge=0, le=1_000_000_000)
    actual_amount: Optional[Decimal] = Field(default=None, ge=0, le=1_000_000_000)
    spent_at: Optional[date] = None

    model_config = {"str_strip_whitespace": True}


class BudgetItemUpdate(BaseModel):
    category: Optional[str] = Field(default=None, min_length=1, max_length=100)
    label: Optional[str] = Field(default=None, min_length=1, max_length=200)
    planned_amount: Optional[Decimal] = Field(default=None, ge=0, le=1_000_000_000)
    actual_amount: Optional[Decimal] = Field(default=None, ge=0, le=1_000_000_000)
    spent_at: Optional[date] = None

    model_config = {"str_strip_whitespace": True}
