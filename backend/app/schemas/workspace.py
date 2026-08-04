from datetime import UTC, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class WorkspaceCreateRequest(BaseModel):
    """Payload for creating a new workspace."""

    name: str = Field(..., min_length=1, max_length=100, description="Tên workspace")

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError("Tên workspace không được để trống hoặc chỉ chứa khoảng trắng.")
        return stripped


class WorkspaceResponse(BaseModel):
    """Schema for workspace response payload."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    owner_id: UUID
    created_at: datetime

    @field_validator("created_at", mode="before")
    @classmethod
    def default_created_at(cls, v: datetime | None) -> datetime:
        if v is None:
            return datetime.now(UTC)
        return v
