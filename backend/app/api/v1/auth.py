from fastapi import APIRouter, Depends, Response, status
from fastapi.security import HTTPAuthorizationCredentials
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user, http_bearer
from app.core.redis import get_redis
from app.models.user import User
from app.schemas.auth import (
    LoginRequest,
    NewAccessTokenResponse,
    RefreshTokenRequest,
    RegisterRequest,
    TokenResponse,
)
from app.schemas.common import SuccessResponse
from app.schemas.user import UserResponse
from app.services.auth import AuthService

router = APIRouter()


def get_auth_service(
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
) -> AuthService:
    """Dependency providing AuthService instance."""
    return AuthService(db=db, redis=redis)


@router.post(
    "/register",
    response_model=SuccessResponse[UserResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user account",
)
async def register(
    dto: RegisterRequest,
    service: AuthService = Depends(get_auth_service),
) -> SuccessResponse[UserResponse]:
    """Register a new user with default MEMBER role."""
    user = await service.register(dto)
    return SuccessResponse(data=user)


@router.post(
    "/login",
    response_model=SuccessResponse[TokenResponse],
    status_code=status.HTTP_200_OK,
    summary="Authenticate user and issue JWT tokens",
)
async def login(
    dto: LoginRequest,
    service: AuthService = Depends(get_auth_service),
) -> SuccessResponse[TokenResponse]:
    """Authenticate user credentials and return access + refresh tokens."""
    token_response = await service.login(dto)
    return SuccessResponse(data=token_response)


@router.post(
    "/refresh",
    response_model=SuccessResponse[NewAccessTokenResponse],
    status_code=status.HTTP_200_OK,
    summary="Refresh access token",
)
async def refresh(
    dto: RefreshTokenRequest,
    service: AuthService = Depends(get_auth_service),
) -> SuccessResponse[NewAccessTokenResponse]:
    """Issue a new access token using a valid refresh token."""
    new_token = await service.refresh(dto)
    return SuccessResponse(data=new_token)


@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Logout user and revoke tokens",
)
async def logout(
    dto: RefreshTokenRequest,
    current_user: User = Depends(get_current_user),
    credentials: HTTPAuthorizationCredentials | None = Depends(http_bearer),
    service: AuthService = Depends(get_auth_service),
) -> Response:
    """Revoke refresh token and current access token."""
    access_token = credentials.credentials if credentials else None
    await service.logout(
        current_user=current_user,
        current_access_token=access_token,
        refresh_token=dto.refresh_token,
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
