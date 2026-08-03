from datetime import UTC, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, field_validator

from app.models.enums import UserRole


class UserResponse(BaseModel):
    """Schema for user response payload (excluding sensitive credentials)."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: EmailStr
    full_name: str
    role: UserRole
    is_active: bool
    created_at: datetime

    @field_validator("created_at", mode="before")
    @classmethod
    def default_created_at(cls, v: datetime | None) -> datetime:
        if v is None:
            return datetime.now(UTC)
        return v
