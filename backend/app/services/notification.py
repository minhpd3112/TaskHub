from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ValidationError
from app.models.user import User
from app.repositories.notification import NotificationRepository
from app.schemas.notification import (
    NotificationSettingsResponse,
    NotificationSettingsUpdateRequest,
)


class NotificationService:
    """Service handling business logic for user notification settings."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.repository = NotificationRepository(db)

    async def get_settings(self, current_user: User) -> NotificationSettingsResponse:
        """Get notification settings for current user, initializing defaults if absent."""
        setting = await self.repository.get_or_create(current_user.id)
        return NotificationSettingsResponse.model_validate(setting)

    async def update_settings(
        self, current_user: User, dto: NotificationSettingsUpdateRequest
    ) -> NotificationSettingsResponse:
        """Update notification settings for current user.

        Raises:
            ValidationError: If task_assigned is set to False (code="INVALID_SETTING").
        """
        if dto.task_assigned is False:
            raise ValidationError(
                message=(
                    "Email thông báo công việc mới (task_assigned) " "là bắt buộc và không thể tắt."
                ),
                code="INVALID_SETTING",
            )

        update_data = dto.model_dump(exclude_unset=True)
        setting = await self.repository.update_settings(current_user.id, **update_data)
        await self.db.commit()
        await self.db.refresh(setting)
        return NotificationSettingsResponse.model_validate(setting)
