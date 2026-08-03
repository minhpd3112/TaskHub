from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.schemas.common import SuccessResponse
from app.schemas.user import ChangePasswordRequest, UserResponse, UserUpdateRequest
from app.services.user import UserService

router = APIRouter()


def get_user_service(
    db: AsyncSession = Depends(get_db),
) -> UserService:
    """Dependency providing UserService instance."""
    return UserService(db=db)


@router.get(
    "/me",
    response_model=SuccessResponse[UserResponse],
    status_code=status.HTTP_200_OK,
    summary="Get current user profile",
)
async def get_me(
    current_user: User = Depends(get_current_user),
    service: UserService = Depends(get_user_service),
) -> SuccessResponse[UserResponse]:
    """Get personal profile of the currently authenticated user."""
    profile = await service.get_profile(current_user)
    return SuccessResponse(data=profile)


@router.patch(
    "/me",
    response_model=SuccessResponse[UserResponse],
    status_code=status.HTTP_200_OK,
    summary="Update current user profile",
)
async def update_me(
    dto: UserUpdateRequest,
    current_user: User = Depends(get_current_user),
    service: UserService = Depends(get_user_service),
) -> SuccessResponse[UserResponse]:
    """Update profile information (e.g. full_name) of the currently authenticated user."""
    updated_profile = await service.update_profile(current_user, dto)
    return SuccessResponse(data=updated_profile)


@router.post(
    "/me/password",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Change current user password",
)
@router.post(
    "/me/change-password",
    status_code=status.HTTP_204_NO_CONTENT,
    include_in_schema=False,
)
async def change_password(
    dto: ChangePasswordRequest,
    current_user: User = Depends(get_current_user),
    service: UserService = Depends(get_user_service),
) -> Response:
    """Change password for the currently authenticated user after validating current password."""
    await service.change_password(current_user, dto)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
