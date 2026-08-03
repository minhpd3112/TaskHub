from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError, UnauthorizedError
from app.core.security import hash_password, verify_password
from app.models.user import User
from app.repositories.user import UserRepository
from app.schemas.user import ChangePasswordRequest, UserResponse, UserUpdateRequest


class UserService:
    """Service handling user profile business logic."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.user_repo = UserRepository(db)

    async def get_profile(self, user: User) -> UserResponse:
        """Retrieve profile information for the current user."""
        return UserResponse.model_validate(user)

    async def update_profile(self, user: User, dto: UserUpdateRequest) -> UserResponse:
        """Update profile information for the current user."""
        updated_user = await self.user_repo.update_by_id(user.id, full_name=dto.full_name)
        if not updated_user:
            raise NotFoundError("User not found.", code="USER_NOT_FOUND")
        return UserResponse.model_validate(updated_user)

    async def change_password(self, user: User, dto: ChangePasswordRequest) -> None:
        """Change password for the current user after validating current password."""
        if not verify_password(dto.current_password, user.hashed_password):
            raise UnauthorizedError("Mật khẩu hiện tại không đúng.", code="WRONG_PASSWORD")

        new_hashed_password = hash_password(dto.new_password)
        await self.user_repo.update_by_id(user.id, hashed_password=new_hashed_password)
