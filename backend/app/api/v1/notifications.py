from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.schemas.common import SuccessResponse
from app.schemas.notification import (
    NotificationSettingsResponse,
    NotificationSettingsUpdateRequest,
)
from app.services.notification import NotificationService

router = APIRouter(prefix="/notifications", tags=["Notifications"])


def get_notification_service(
    db: AsyncSession = Depends(get_db),
) -> NotificationService:
    """Dependency providing NotificationService instance."""
    return NotificationService(db=db)


@router.get(
    "/settings",
    response_model=SuccessResponse[NotificationSettingsResponse],
    status_code=status.HTTP_200_OK,
    summary="Xem cài đặt thông báo email của người dùng hiện tại",
    description="Lấy danh sách các cài đặt nhận email thông báo của tài khoản đang đăng nhập.",
    operation_id="layCaiDatThongBao",
)
async def get_notification_settings(
    current_user: User = Depends(get_current_user),
    service: NotificationService = Depends(get_notification_service),
) -> SuccessResponse[NotificationSettingsResponse]:
    """Retrieve notification settings for current authenticated user."""
    settings = await service.get_settings(current_user=current_user)
    return SuccessResponse(data=settings)


@router.patch(
    "/settings",
    response_model=SuccessResponse[NotificationSettingsResponse],
    status_code=status.HTTP_200_OK,
    summary="Cập nhật cài đặt thông báo email của người dùng hiện tại",
    description="Cập nhật tùy chọn nhận email thông báo (task_assigned không được phép tắt).",
    operation_id="capNhatCaiDatThongBao",
)
async def update_notification_settings(
    dto: NotificationSettingsUpdateRequest,
    current_user: User = Depends(get_current_user),
    service: NotificationService = Depends(get_notification_service),
) -> SuccessResponse[NotificationSettingsResponse]:
    """Update notification settings for current authenticated user."""
    settings = await service.update_settings(current_user=current_user, dto=dto)
    return SuccessResponse(data=settings)
