from pydantic import BaseModel, ConfigDict, field_validator


class NotificationSettingsResponse(BaseModel):
    """Schema for user notification settings response."""

    task_assigned: bool = True
    task_status_changed: bool = True
    task_commented: bool = True

    model_config = ConfigDict(from_attributes=True)


class NotificationSettingsUpdateRequest(BaseModel):
    """Schema for updating user notification settings."""

    task_assigned: bool | None = None
    task_status_changed: bool | None = None
    task_commented: bool | None = None

    @field_validator("task_assigned", mode="after")
    @classmethod
    def validate_task_assigned(cls, v: bool | None) -> bool | None:
        if v is False:
            raise ValueError(
                "Email thông báo công việc mới (task_assigned) là bắt buộc và không thể tắt."
            )
        return v
