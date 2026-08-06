from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.user import User


class UserNotificationSetting(Base):
    """Cài đặt thông báo email của người dùng."""

    __tablename__ = "user_notification_settings"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    task_assigned: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )
    task_status_changed: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )
    task_commented: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # Relationship
    user: Mapped[User] = relationship("User", back_populates="notification_setting")
