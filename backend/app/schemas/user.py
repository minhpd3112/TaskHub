from datetime import UTC, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

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
    updated_at: datetime | None = None

    @field_validator("created_at", mode="before")
    @classmethod
    def default_created_at(cls, v: datetime | None) -> datetime:
        if v is None:
            return datetime.now(UTC)
        return v


class UserUpdateRequest(BaseModel):
    """Payload for updating user profile."""

    full_name: str = Field(..., min_length=1, max_length=100, description="Full name")

    @field_validator("full_name")
    @classmethod
    def validate_full_name(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError("Full name cannot be empty or whitespace only.")
        return stripped


class ChangePasswordRequest(BaseModel):
    """Payload for changing user password."""

    current_password: str = Field(..., min_length=1, description="Current password")
    new_password: str = Field(..., min_length=8, max_length=128, description="New password")

    @field_validator("new_password")
    @classmethod
    def validate_new_password_strength(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters long.")
        if not any(c.isupper() for c in v):
            raise ValueError("Password must contain at least one uppercase letter.")
        if not any(c.islower() for c in v):
            raise ValueError("Password must contain at least one lowercase letter.")
        if not any(c.isdigit() for c in v):
            raise ValueError("Password must contain at least one digit.")
        if not any(not c.isalnum() for c in v):
            raise ValueError("Password must contain at least one special character.")
        return v
