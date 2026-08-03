from datetime import UTC, datetime
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.core.exceptions import NotFoundError, UnauthorizedError
from app.core.security import hash_password, verify_password
from app.models.enums import UserRole
from app.models.user import User
from app.schemas.user import ChangePasswordRequest, UserUpdateRequest
from app.services.user import UserService


@pytest.fixture
def mock_db() -> AsyncMock:
    """Mock AsyncSession for unit testing."""
    return AsyncMock()


@pytest.fixture
def user_service(mock_db: AsyncMock) -> UserService:
    """Instantiate UserService with mock AsyncSession."""
    return UserService(db=mock_db)


@pytest.fixture
def sample_user() -> User:
    """Sample User instance for unit testing."""
    return User(
        id=uuid4(),
        email="testuser@taskhub.io",
        full_name="Original Name",
        hashed_password=hash_password("Password123!"),
        role=UserRole.MEMBER,
        is_active=True,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )


@pytest.mark.asyncio
async def test_get_profile_success(user_service: UserService, sample_user: User) -> None:
    """Test retrieving user profile."""
    profile = await user_service.get_profile(sample_user)

    assert profile.id == sample_user.id
    assert profile.email == sample_user.email
    assert profile.full_name == "Original Name"
    assert profile.role == UserRole.MEMBER
    assert profile.is_active is True


@pytest.mark.asyncio
async def test_update_profile_success(user_service: UserService, sample_user: User) -> None:
    """Test updating user profile full_name."""
    updated_user = User(
        id=sample_user.id,
        email=sample_user.email,
        full_name="Updated Name",
        hashed_password=sample_user.hashed_password,
        role=sample_user.role,
        is_active=sample_user.is_active,
        created_at=sample_user.created_at,
        updated_at=datetime.now(UTC),
    )
    user_service.user_repo.update_by_id = AsyncMock(return_value=updated_user)

    dto = UserUpdateRequest(full_name="Updated Name")
    result = await user_service.update_profile(sample_user, dto)

    user_service.user_repo.update_by_id.assert_called_once_with(
        sample_user.id, full_name="Updated Name"
    )
    assert result.full_name == "Updated Name"


@pytest.mark.asyncio
async def test_update_profile_user_not_found(user_service: UserService, sample_user: User) -> None:
    """Test updating user profile when user is not found in database."""
    user_service.user_repo.update_by_id = AsyncMock(return_value=None)

    dto = UserUpdateRequest(full_name="New Name")
    with pytest.raises(NotFoundError) as exc_info:
        await user_service.update_profile(sample_user, dto)

    assert exc_info.value.code == "USER_NOT_FOUND"


@pytest.mark.asyncio
async def test_change_password_success(user_service: UserService, sample_user: User) -> None:
    """Test changing user password with valid current password."""
    user_service.user_repo.update_by_id = AsyncMock()

    dto = ChangePasswordRequest(current_password="Password123!", new_password="NewPassword456!")
    await user_service.change_password(sample_user, dto)

    user_service.user_repo.update_by_id.assert_called_once()
    call_args = user_service.user_repo.update_by_id.call_args
    updated_id, kwargs = call_args[0][0], call_args[1]
    assert updated_id == sample_user.id
    assert "hashed_password" in kwargs
    assert verify_password("NewPassword456!", kwargs["hashed_password"])


@pytest.mark.asyncio
async def test_change_password_wrong_current_password(
    user_service: UserService, sample_user: User
) -> None:
    """Test changing user password with invalid current password."""
    dto = ChangePasswordRequest(current_password="WrongPassword!", new_password="NewPassword456!")
    with pytest.raises(UnauthorizedError) as exc_info:
        await user_service.change_password(sample_user, dto)

    assert exc_info.value.code == "WRONG_PASSWORD"
