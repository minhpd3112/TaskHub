from __future__ import annotations

import uuid
from datetime import date
from typing import TYPE_CHECKING

from sqlalchemy import Date, ForeignKey, Index, String, Text
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin
from app.models.enums import TaskPriority, TaskStatus

if TYPE_CHECKING:
    from app.models.comment import Comment
    from app.models.label import Label
    from app.models.project import Project
    from app.models.user import User


class Task(Base, UUIDMixin, TimestampMixin):
    """Task ORM model."""

    __tablename__ = "tasks"
    __table_args__ = (
        Index("ix_tasks_project_status", "project_id", "status"),
        Index("ix_tasks_project_priority", "project_id", "priority"),
        Index("ix_tasks_project_assignee", "project_id", "assignee_id"),
    )

    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    assignee_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    created_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    title: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
    )
    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    status: Mapped[TaskStatus] = mapped_column(
        SAEnum(TaskStatus, name="task_status"),
        nullable=False,
        default=TaskStatus.TODO,
        index=True,
    )
    priority: Mapped[TaskPriority] = mapped_column(
        SAEnum(TaskPriority, name="task_priority"),
        nullable=False,
        default=TaskPriority.MEDIUM,
        index=True,
    )
    due_date: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
    )

    # Relationships
    project: Mapped[Project] = relationship(
        "Project",
        back_populates="tasks",
    )
    assignee: Mapped[User] = relationship(
        "User",
        foreign_keys=[assignee_id],
        back_populates="assigned_tasks",
    )
    creator: Mapped[User] = relationship(
        "User",
        foreign_keys=[created_by],
        back_populates="created_tasks",
    )
    labels: Mapped[list[Label]] = relationship(
        "Label",
        secondary="task_labels",
        back_populates="tasks",
    )
    comments: Mapped[list[Comment]] = relationship(
        "Comment",
        back_populates="task",
        cascade="all, delete-orphan",
    )
