"""Pydantic schemas package."""

from app.schemas.auth import (
    LoginRequest,
    NewAccessTokenResponse,
    RefreshTokenRequest,
    RegisterRequest,
    TokenResponse,
)
from app.schemas.common import (
    ErrorBody,
    ErrorDetail,
    ErrorResponse,
    PaginatedResponse,
    PaginationMeta,
    SuccessResponse,
)
from app.schemas.project import ProjectCreateRequest, ProjectResponse
from app.schemas.user import UserResponse
from app.schemas.workspace import WorkspaceCreateRequest, WorkspaceResponse

__all__ = [
    "PaginationMeta",
    "SuccessResponse",
    "PaginatedResponse",
    "ErrorDetail",
    "ErrorBody",
    "ErrorResponse",
    "UserResponse",
    "WorkspaceCreateRequest",
    "WorkspaceResponse",
    "RegisterRequest",
    "LoginRequest",
    "RefreshTokenRequest",
    "TokenResponse",
    "NewAccessTokenResponse",
    "ProjectCreateRequest",
    "ProjectResponse",
]
