from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


TargetType = Literal["project", "task"]


class CommentCreate(BaseModel):
    target_type: TargetType
    target_id: UUID
    body: str = Field(min_length=1, max_length=5000)

    @field_validator("body")
    @classmethod
    def body_must_not_be_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("comment body cannot be blank")
        return value
