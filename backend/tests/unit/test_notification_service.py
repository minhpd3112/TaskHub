from datetime import UTC, datetime
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.core.exceptions import ValidationError
from app.models.enums import UserRole
from app.models.notification import UserNotificationSetting
from app.models.user import User
from app.schemas.notification import NotificationSettingsUpdateRequest
from app.services.notification import NotificationService


@pytest.fixture
def mock_db() -> AsyncMock:
    """Mock AsyncSession for unit testing."""
    return AsyncMock()


@pytest.fixture
def notification_service(mock_db: AsyncMock) -> NotificationService:
    """Instantiate NotificationService with mock AsyncSession."""
    return NotificationService(db=mock_db)


@pytest.fixture
def sample_user() -> User:
    """Sample User instance for unit testing."""
    return User(
        id=uuid4(),
        email="testuser@taskhub.io",
        full_name="Test User",
        hashed_password="hashedpassword",
        role=UserRole.MEMBER,
        is_active=True,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )


@pytest.mark.asyncio
async def test_get_settings_default_values(
    notification_service: NotificationService, sample_user: User
) -> None:
    """Test retrieving notification settings returns default values (True, True, True)."""
    default_setting = UserNotificationSetting(
        user_id=sample_user.id,
        task_assigned=True,
        task_status_changed=True,
        task_commented=True,
        updated_at=datetime.now(UTC),
    )
    notification_service.repository.get_or_create = AsyncMock(return_value=default_setting)

    result = await notification_service.get_settings(sample_user)

    notification_service.repository.get_or_create.assert_called_once_with(sample_user.id)
    assert result.task_assigned is True
    assert result.task_status_changed is True
    assert result.task_commented is True


@pytest.mark.asyncio
async def test_update_settings_success(
    notification_service: NotificationService, sample_user: User
) -> None:
    """Test updating task_status_changed and task_commented options successfully."""
    updated_setting = UserNotificationSetting(
        user_id=sample_user.id,
        task_assigned=True,
        task_status_changed=False,
        task_commented=False,
        updated_at=datetime.now(UTC),
    )
    notification_service.repository.update_settings = AsyncMock(return_value=updated_setting)

    dto = NotificationSettingsUpdateRequest(
        task_status_changed=False,
        task_commented=False,
    )
    result = await notification_service.update_settings(sample_user, dto)

    notification_service.repository.update_settings.assert_called_once_with(
        sample_user.id, task_status_changed=False, task_commented=False
    )
    assert result.task_assigned is True
    assert result.task_status_changed is False
    assert result.task_commented is False


@pytest.mark.asyncio
async def test_update_settings_task_assigned_false_raises_validation_error(
    notification_service: NotificationService, sample_user: User
) -> None:
    """Test updating task_assigned to False raises ValidationError with code INVALID_SETTING."""
    dto = NotificationSettingsUpdateRequest.model_construct(task_assigned=False)

    with pytest.raises(ValidationError) as exc_info:
        await notification_service.update_settings(sample_user, dto)

    assert exc_info.value.code == "INVALID_SETTING"
    assert "task_assigned" in exc_info.value.message
