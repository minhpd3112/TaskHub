from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.enums import ProjectStatus


class ProjectCreateRequest(BaseModel):
    """Payload for creating a new project within a workspace."""

    name: str = Field(
        ...,
        min_length=1,
        max_length=200,
        description="Tên project (1-200 ký tự)",
    )
    description: str | None = Field(
        default=None,
        max_length=2000,
        description="Mô tả project (tối đa 2000 ký tự)",
    )

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError("Project name cannot be empty or whitespace only.")
        return stripped


class ProjectUpdateRequest(BaseModel):
    """Payload for updating an existing project."""

    name: str | None = Field(
        default=None,
        min_length=1,
        max_length=200,
        description="Tên project mới (1-200 ký tự)",
    )
    description: str | None = Field(
        default=None,
        max_length=2000,
        description="Mô tả project mới (tối đa 2000 ký tự)",
    )

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str | None) -> str | None:
        if v is None:
            return None
        stripped = v.strip()
        if not stripped:
            raise ValueError("Project name cannot be empty or whitespace only.")
        return stripped


class ProjectResponse(BaseModel):
    """Response payload representing a project."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    workspace_id: UUID
    name: str
    description: str | None = None
    status: ProjectStatus
    created_at: datetime
    updated_at: datetime | None = None


class ProjectListItemResponse(BaseModel):
    """Response payload representing a project item in list response."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    workspace_id: UUID
    name: str
    description: str | None = None
    status: ProjectStatus
    task_count: int = 0
    created_at: datetime
    updated_at: datetime | None = None


class ProjectDetailResponse(BaseModel):
    """Response payload representing detailed project info."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    workspace_id: UUID
    name: str
    description: str | None = None
    status: ProjectStatus
    task_count: int = 0
    created_at: datetime
    updated_at: datetime | None = None
