from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Enum as SAEnum
from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin
from app.models.enums import ProjectStatus

if TYPE_CHECKING:
    from app.models.label import Label
    from app.models.task import Task
    from app.models.workspace import Workspace


class Project(Base, UUIDMixin, TimestampMixin):
    """Project ORM model."""

    __tablename__ = "projects"

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
    )
    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    status: Mapped[ProjectStatus] = mapped_column(
        SAEnum(ProjectStatus, name="project_status"),
        nullable=False,
        default=ProjectStatus.ACTIVE,
        index=True,
    )

    # Relationships
    workspace: Mapped[Workspace] = relationship(
        "Workspace",
        back_populates="projects",
    )
    tasks: Mapped[list[Task]] = relationship(
        "Task",
        back_populates="project",
        cascade="all, delete-orphan",
    )
    labels: Mapped[list[Label]] = relationship(
        "Label",
        back_populates="project",
        cascade="all, delete-orphan",
    )
