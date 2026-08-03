from datetime import UTC, datetime
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.core.exceptions import ConflictError, UnauthorizedError
from app.core.security import create_access_token, create_refresh_token, hash_password
from app.models.enums import UserRole
from app.models.user import User
from app.schemas.auth import LoginRequest, RefreshTokenRequest, RegisterRequest
from app.services.auth import AuthService


@pytest.fixture
def mock_db() -> AsyncMock:
    """Mock AsyncSession for unit testing."""
    return AsyncMock()


@pytest.fixture
def mock_redis() -> AsyncMock:
    """Mock Redis client for unit testing."""
    redis = AsyncMock()
    redis.get.return_value = None
    redis.setex.return_value = True
    return redis


@pytest.fixture
def auth_service(mock_db: AsyncMock, mock_redis: AsyncMock) -> AuthService:
    """Instantiate AuthService with mock dependencies."""
    return AuthService(db=mock_db, redis=mock_redis)


@pytest.mark.asyncio
async def test_register_success(auth_service: AuthService, mock_db: AsyncMock) -> None:
    """Test successful user registration."""
    auth_service.user_repo.is_email_taken = AsyncMock(return_value=False)
    created_user = User(
        id=uuid4(),
        email="newuser@example.com",
        full_name="New User",
        hashed_password=hash_password("Password123!"),
        role=UserRole.MEMBER,
        is_active=True,
        created_at=datetime.now(UTC),
    )
    auth_service.user_repo.create = AsyncMock(return_value=created_user)

    dto = RegisterRequest(
        email="newuser@example.com",
        full_name="New User",
        password="Password123!",
    )
    result = await auth_service.register(dto)

    assert result.email == "newuser@example.com"
    assert result.full_name == "New User"
    assert result.role == UserRole.MEMBER
    assert result.is_active is True


@pytest.mark.asyncio
async def test_register_duplicate_email(auth_service: AuthService) -> None:
    """Test registration fails when email is already taken."""
    auth_service.user_repo.is_email_taken = AsyncMock(return_value=True)

    dto = RegisterRequest(
        email="existing@example.com",
        full_name="Existing User",
        password="Password123!",
    )

    with pytest.raises(ConflictError) as exc_info:
        await auth_service.register(dto)

    assert exc_info.value.code == "EMAIL_ALREADY_EXISTS"


@pytest.mark.asyncio
async def test_login_success(auth_service: AuthService) -> None:
    """Test successful login with valid credentials."""
    user = User(
        id=uuid4(),
        email="user@example.com",
        full_name="Valid User",
        hashed_password=hash_password("Password123!"),
        role=UserRole.MEMBER,
        is_active=True,
        created_at=datetime.now(UTC),
    )
    auth_service.user_repo.get_by_email = AsyncMock(return_value=user)

    dto = LoginRequest(email="user@example.com", password="Password123!")
    result = await auth_service.login(dto)

    assert result.access_token is not None
    assert result.refresh_token is not None
    assert result.token_type == "bearer"
    assert result.user.email == "user@example.com"


@pytest.mark.asyncio
async def test_login_invalid_password(auth_service: AuthService) -> None:
    """Test login failure with wrong password."""
    user = User(
        id=uuid4(),
        email="user@example.com",
        full_name="Valid User",
        hashed_password=hash_password("Password123!"),
        role=UserRole.MEMBER,
        is_active=True,
        created_at=datetime.now(UTC),
    )
    auth_service.user_repo.get_by_email = AsyncMock(return_value=user)

    dto = LoginRequest(email="user@example.com", password="WrongPassword!")

    with pytest.raises(UnauthorizedError) as exc_info:
        await auth_service.login(dto)

    assert exc_info.value.code == "INVALID_CREDENTIALS"


@pytest.mark.asyncio
async def test_login_inactive_user(auth_service: AuthService) -> None:
    """Test login failure when user account is disabled/inactive."""
    user = User(
        id=uuid4(),
        email="inactive@example.com",
        full_name="Inactive User",
        hashed_password=hash_password("Password123!"),
        role=UserRole.MEMBER,
        is_active=False,
        created_at=datetime.now(UTC),
    )
    auth_service.user_repo.get_by_email = AsyncMock(return_value=user)

    dto = LoginRequest(email="inactive@example.com", password="Password123!")

    with pytest.raises(UnauthorizedError) as exc_info:
        await auth_service.login(dto)

    assert exc_info.value.code == "ACCOUNT_INACTIVE"


@pytest.mark.asyncio
async def test_refresh_success(auth_service: AuthService) -> None:
    """Test successful access token refresh."""
    user_id = uuid4()
    user = User(
        id=user_id,
        email="user@example.com",
        full_name="User",
        hashed_password="hash",
        role=UserRole.MEMBER,
        is_active=True,
        created_at=datetime.now(UTC),
    )
    auth_service.user_repo.get_by_id = AsyncMock(return_value=user)

    refresh_token = create_refresh_token(subject=str(user_id))
    dto = RefreshTokenRequest(refresh_token=refresh_token)

    result = await auth_service.refresh(dto)

    assert result.access_token is not None
    assert result.token_type == "bearer"


@pytest.mark.asyncio
async def test_refresh_revoked_token(auth_service: AuthService, mock_redis: AsyncMock) -> None:
    """Test token refresh fails if refresh token is in Redis blacklist."""
    user_id = uuid4()
    refresh_token = create_refresh_token(subject=str(user_id))
    mock_redis.get.return_value = "1"

    dto = RefreshTokenRequest(refresh_token=refresh_token)

    with pytest.raises(UnauthorizedError) as exc_info:
        await auth_service.refresh(dto)

    assert exc_info.value.code == "REFRESH_TOKEN_INVALID"


@pytest.mark.asyncio
async def test_logout_blacklists_tokens(auth_service: AuthService, mock_redis: AsyncMock) -> None:
    """Test logout adds both refresh token and access token JTIs to Redis blacklist."""
    user = User(
        id=uuid4(),
        email="user@example.com",
        full_name="User",
        hashed_password="hash",
        role=UserRole.MEMBER,
        is_active=True,
        created_at=datetime.now(UTC),
    )
    access_token = create_access_token(subject=str(user.id))
    refresh_token = create_refresh_token(subject=str(user.id))

    await auth_service.logout(
        current_user=user,
        current_access_token=access_token,
        refresh_token=refresh_token,
    )

    assert mock_redis.setex.call_count == 2
