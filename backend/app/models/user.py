from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Enum as SAEnum
from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin
from app.models.enums import UserRole

if TYPE_CHECKING:
    from app.models.comment import Comment
    from app.models.task import Task
    from app.models.workspace import Workspace, WorkspaceMember


class User(Base, UUIDMixin, TimestampMixin):
    """User ORM model representing system users."""

    __tablename__ = "users"

    email: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        unique=True,
        index=True,
    )
    full_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )
    hashed_password: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    role: Mapped[UserRole] = mapped_column(
        SAEnum(UserRole, name="user_role"),
        nullable=False,
        default=UserRole.MEMBER,
    )
    is_active: Mapped[bool] = mapped_column(
        default=True,
        nullable=False,
    )

    # Relationships
    owned_workspaces: Mapped[list[Workspace]] = relationship(
        "Workspace",
        back_populates="owner",
        lazy="select",
    )
    workspace_memberships: Mapped[list[WorkspaceMember]] = relationship(
        "WorkspaceMember",
        back_populates="user",
        lazy="select",
    )
    assigned_tasks: Mapped[list[Task]] = relationship(
        "Task",
        foreign_keys="Task.assignee_id",
        back_populates="assignee",
        lazy="select",
    )
    created_tasks: Mapped[list[Task]] = relationship(
        "Task",
        foreign_keys="Task.created_by",
        back_populates="creator",
        lazy="select",
    )
    comments: Mapped[list[Comment]] = relationship(
        "Comment",
        back_populates="author",
        lazy="select",
    )
