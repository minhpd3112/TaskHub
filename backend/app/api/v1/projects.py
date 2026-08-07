from uuid import UUID

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.enums import UserRole
from app.models.user import User
from app.schemas.common import SuccessResponse
from app.schemas.project import (
    ProjectDetailResponse,
    ProjectResponse,
    ProjectUpdateRequest,
)
from app.services.project import ProjectService

router = APIRouter()


def get_project_service(
    db: AsyncSession = Depends(get_db),
) -> ProjectService:
    """Dependency providing ProjectService instance."""
    return ProjectService(db=db)


@router.get(
    "/{project_id}",
    response_model=SuccessResponse[ProjectDetailResponse],
    status_code=status.HTTP_200_OK,
    summary="Xem chi tiết dự án",
    description=(
        "Cho phép thành viên Workspace xem chi tiết dự án kèm số lượng task. "
        "Với vai trò EDITOR, chỉ được xem dự án có ít nhất 1 task do mình phụ trách "
        "(nếu không có task nào sẽ nhận lỗi 404 NOT_FOUND)."
    ),
    operation_id="layDuAn",
)
async def get_project_detail(
    project_id: UUID,
    current_user: User = Depends(get_current_user),
    service: ProjectService = Depends(get_project_service),
) -> SuccessResponse[ProjectDetailResponse]:
    """Retrieve detailed information of a project."""
    project, task_count = await service.get_project_detail(
        project_id=project_id,
        current_user_id=current_user.id,
        is_admin=(current_user.role == UserRole.ADMIN),
    )
    data = ProjectDetailResponse(
        id=project.id,
        workspace_id=project.workspace_id,
        name=project.name,
        description=project.description,
        status=project.status,
        task_count=task_count,
        created_at=project.created_at,
        updated_at=project.updated_at,
    )
    return SuccessResponse(data=data)


@router.patch(
    "/{project_id}",
    response_model=SuccessResponse[ProjectResponse],
    status_code=status.HTTP_200_OK,
    summary="Cập nhật dự án",
    description="Cho phép OWNER (hoặc System ADMIN) cập nhật tên và mô tả dự án.",
    operation_id="capNhatDuAn",
)
async def update_project(
    project_id: UUID,
    dto: ProjectUpdateRequest,
    current_user: User = Depends(get_current_user),
    service: ProjectService = Depends(get_project_service),
) -> SuccessResponse[ProjectResponse]:
    """Update project name and/or description."""
    project = await service.update_project(
        project_id=project_id,
        dto=dto,
        current_user_id=current_user.id,
        is_admin=(current_user.role == UserRole.ADMIN),
    )
    return SuccessResponse(data=ProjectResponse.model_validate(project))


@router.patch(
    "/{project_id}/archive",
    response_model=SuccessResponse[ProjectResponse],
    status_code=status.HTTP_200_OK,
    summary="Thay đổi trạng thái/Archive dự án",
    description=(
        "Cho phép OWNER (hoặc System ADMIN) chuyển trạng thái dự án giữa ACTIVE và ARCHIVED."
    ),
    operation_id="doiTrangThaiDuAn",
)
async def archive_project(
    project_id: UUID,
    current_user: User = Depends(get_current_user),
    service: ProjectService = Depends(get_project_service),
) -> SuccessResponse[ProjectResponse]:
    """Archive or toggle project active/archived status."""
    project = await service.archive_project(
        project_id=project_id,
        current_user_id=current_user.id,
        is_admin=(current_user.role == UserRole.ADMIN),
    )
    return SuccessResponse(data=ProjectResponse.model_validate(project))


@router.delete(
    "/{project_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    summary="Xóa dự án",
    description=(
        "Cho phép OWNER (hoặc System ADMIN) xóa dự án và CASCADE xóa toàn bộ task, label, "
        "comment con."
    ),
    operation_id="xoaDuAn",
)
async def delete_project(
    project_id: UUID,
    current_user: User = Depends(get_current_user),
    service: ProjectService = Depends(get_project_service),
) -> Response:
    """Delete project permanently."""
    await service.delete_project(
        project_id=project_id,
        current_user_id=current_user.id,
        is_admin=(current_user.role == UserRole.ADMIN),
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
