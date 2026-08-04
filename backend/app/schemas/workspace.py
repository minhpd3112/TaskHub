from datetime import UTC, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.models.enums import WorkspaceRole


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


class UserWorkspaceResponse(BaseModel):
    """Response schema for a workspace item in current user's workspace list."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    owner_id: UUID
    role: WorkspaceRole
    created_at: datetime

    @field_validator("created_at", mode="before")
    @classmethod
    def default_created_at(cls, v: datetime | None) -> datetime:
        if v is None:
            return datetime.now(UTC)
        return v


class MemberInviteRequest(BaseModel):
    """Payload for inviting a user to a workspace."""

    email: EmailStr = Field(..., description="Email người dùng cần mời")
    role: WorkspaceRole = Field(default=WorkspaceRole.VIEWER, description="Vai trò trong workspace")


class MemberUpdateRoleRequest(BaseModel):
    """Payload for updating a workspace member's role."""

    role: WorkspaceRole = Field(..., description="Vai trò mới trong workspace")


class WorkspaceMemberResponse(BaseModel):
    """Response schema for workspace member payload."""

    model_config = ConfigDict(from_attributes=True)

    workspace_id: UUID
    user_id: UUID
    role: WorkspaceRole
    joined_at: datetime

    @field_validator("joined_at", mode="before")
    @classmethod
    def default_joined_at(cls, v: datetime | None) -> datetime:
        if v is None:
            return datetime.now(UTC)
        return v


class WorkspaceMemberDetailResponse(BaseModel):
    """Response schema for detailed workspace member payload including user info."""

    model_config = ConfigDict(from_attributes=True)

    user_id: UUID
    email: str
    full_name: str
    role: WorkspaceRole
    joined_at: datetime

    @field_validator("joined_at", mode="before")
    @classmethod
    def default_joined_at(cls, v: datetime | None) -> datetime:
        if v is None:
            return datetime.now(UTC)
        return v
