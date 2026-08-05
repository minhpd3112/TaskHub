import re
from uuid import UUID

from pydantic import BaseModel, ConfigDict, field_validator

HEX_COLOR_REGEX = re.compile(r"^#[0-9A-Fa-f]{6}$")


class LabelCreateRequest(BaseModel):
    """Schema for creating a label in a project."""

    name: str
    color: str

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        trimmed = v.strip()
        if not trimmed:
            raise ValueError("Name must not be empty or contain only whitespace")
        if len(trimmed) > 50:
            raise ValueError("Name must not exceed 50 characters")
        return trimmed

    @field_validator("color")
    @classmethod
    def validate_color(cls, v: str) -> str:
        if not HEX_COLOR_REGEX.match(v):
            raise ValueError("Color must be a valid 7-character hex string (#RRGGBB)")
        return v


class LabelResponse(BaseModel):
    """Schema for label response representation."""

    id: UUID
    project_id: UUID
    name: str
    color: str

    model_config = ConfigDict(from_attributes=True)


class LabelAssignResponse(BaseModel):
    """Response when a label is assigned to a task."""

    task_id: UUID
    label_id: UUID
    label: LabelResponse

    model_config = ConfigDict(from_attributes=True)
