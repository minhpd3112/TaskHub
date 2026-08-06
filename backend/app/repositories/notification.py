from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.notification import UserNotificationSetting
from app.repositories.base import BaseRepository


class NotificationRepository(BaseRepository[UserNotificationSetting]):
    """Repository handling database operations for UserNotificationSetting entities."""

    def __init__(self, db: AsyncSession) -> None:
        super().__init__(UserNotificationSetting, db)

    async def get_by_user_id(self, user_id: UUID) -> UserNotificationSetting | None:
        """Retrieve notification settings for a specific user."""
        stmt = select(UserNotificationSetting).where(UserNotificationSetting.user_id == user_id)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_or_create(self, user_id: UUID) -> UserNotificationSetting:
        """Retrieve notification settings for a user, or create default settings if absent."""
        setting = await self.get_by_user_id(user_id)
        if setting is None:
            setting = UserNotificationSetting(
                user_id=user_id,
                task_assigned=True,
                task_status_changed=True,
                task_commented=True,
            )
            self.db.add(setting)
            await self.db.flush()
        return setting

    async def update_settings(self, user_id: UUID, **kwargs: bool) -> UserNotificationSetting:
        """Update notification settings for a user."""
        setting = await self.get_or_create(user_id)
        for key, value in kwargs.items():
            if value is not None and hasattr(setting, key):
                setattr(setting, key, value)
        await self.db.flush()
        return setting
