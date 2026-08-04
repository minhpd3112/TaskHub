from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.enums import UserRole
from app.models.user import User
from app.schemas.common import SuccessResponse
from app.schemas.project import ProjectDetailResponse
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
    description="Cho phép thành viên Workspace xem chi tiết dự án kèm số lượng task.",
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
