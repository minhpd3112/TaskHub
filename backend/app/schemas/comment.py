from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, field_validator


class CommentCreateRequest(BaseModel):
    """Schema for adding a comment to a task."""

    content: str

    @field_validator("content")
    @classmethod
    def validate_content(cls, v: str) -> str:
        trimmed = v.strip()
        if not trimmed:
            raise ValueError("Content must not be empty or contain only whitespace")
        if len(trimmed) > 5000:
            raise ValueError("Content must not exceed 5000 characters")
        return trimmed


class CommentAuthorResponse(BaseModel):
    """Schema for comment author details."""

    id: UUID
    full_name: str

    model_config = ConfigDict(from_attributes=True)


class CommentResponse(BaseModel):
    """Schema for comment response object."""

    id: UUID
    task_id: UUID
    author_id: UUID
    author: CommentAuthorResponse
    content: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
