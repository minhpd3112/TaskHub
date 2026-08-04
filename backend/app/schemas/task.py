from datetime import date, datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.enums import TaskPriority, TaskStatus


class TaskCreateRequest(BaseModel):
    """Payload for creating a new task within a project."""

    title: str = Field(
        ...,
        min_length=1,
        max_length=500,
        description="Tiêu đề task (1-500 ký tự)",
    )
    description: str | None = Field(
        default=None,
        max_length=5000,
        description="Mô tả task (tối đa 5000 ký tự)",
    )
    status: TaskStatus = Field(
        default=TaskStatus.TODO,
        description="Trạng thái task (mặc định TODO)",
    )
    priority: TaskPriority = Field(
        default=TaskPriority.MEDIUM,
        description="Mức độ ưu tiên (mặc định MEDIUM)",
    )
    due_date: date | None = Field(
        default=None,
        description="Hạn hoàn thành (YYYY-MM-DD)",
    )
    assignee_id: UUID = Field(
        ...,
        description="ID của thành viên phụ trách (bắt buộc thuộc workspace chứa project)",
    )

    @field_validator("title")
    @classmethod
    def validate_title(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError("Task title cannot be empty or whitespace only.")
        return stripped


class AssigneeResponse(BaseModel):
    """Summarized response model for task assignee user."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    full_name: str
    email: str


class TaskResponse(BaseModel):
    """Response payload representing a task."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    project_id: UUID
    title: str
    description: str | None = None
    status: TaskStatus
    priority: TaskPriority
    due_date: date | None = None
    assignee_id: UUID
    assignee: AssigneeResponse | None = None
    created_by: UUID
    labels: list[Any] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime | None = None
