from datetime import date, datetime
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


class TaskUpdateRequest(BaseModel):
    """Payload for updating an existing task."""

    title: str | None = None
    description: str | None = None
    status: TaskStatus | None = None
    priority: TaskPriority | None = None
    assignee_id: UUID | None = None
    due_date: date | None = None

    @field_validator("title")
    @classmethod
    def validate_title(cls, v: str | None) -> str | None:
        if v is not None:
            v = v.strip()
            if not v or len(v) > 500:
                raise ValueError("Title must not be empty and cannot exceed 500 characters")
        return v

    @field_validator("description")
    @classmethod
    def validate_description(cls, v: str | None) -> str | None:
        if v is not None and len(v) > 5000:
            raise ValueError("Description cannot exceed 5000 characters")
        return v


class TaskStatusUpdateRequest(BaseModel):
    """Schema cập nhật trạng thái task (doiTrangThaiCongViec)."""

    status: TaskStatus


class TaskPriorityUpdateRequest(BaseModel):
    """Schema cập nhật mức độ ưu tiên task (doiUuTienCongViec)."""

    priority: TaskPriority


class AssigneeResponse(BaseModel):
    """Summarized response model for task assignee user."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    full_name: str
    email: str


class CreatorResponse(BaseModel):
    """Summarized response model for task creator user."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    full_name: str
    email: str


class LabelResponse(BaseModel):
    """Summarized response model for task label."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    color: str


class CommentAuthorResponse(BaseModel):
    """Summarized response model for comment author user."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    full_name: str
    email: str


class CommentResponse(BaseModel):
    """Summarized response model for task comment."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    content: str
    author: CommentAuthorResponse
    created_at: datetime


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
    labels: list[LabelResponse] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime | None = None


class TaskDetailResponse(BaseModel):
    """Response payload representing detailed task information."""

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
    creator: CreatorResponse | None = None
    labels: list[LabelResponse] = Field(default_factory=list)
    comments: list[CommentResponse] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime | None = None
