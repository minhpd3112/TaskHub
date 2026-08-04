from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import require_workspace_role
from app.models.enums import WorkspaceRole
from app.models.workspace import WorkspaceMember
from app.schemas.common import SuccessResponse
from app.schemas.project import ProjectCreateRequest, ProjectResponse
from app.services.project import ProjectService

router = APIRouter()


def get_project_service(
    db: AsyncSession = Depends(get_db),
) -> ProjectService:
    """Dependency providing ProjectService instance."""
    return ProjectService(db=db)


@router.post(
    "/{workspace_id}/projects",
    response_model=SuccessResponse[ProjectResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Tạo project mới trong workspace",
    description=(
        "Cho phép thành viên có vai trò EDITOR hoặc OWNER "
        "tạo một dự án mới trong Workspace."
    ),

)
async def create_project(
    workspace_id: UUID,
    dto: ProjectCreateRequest,
    member: WorkspaceMember = Depends(require_workspace_role(WorkspaceRole.EDITOR)),
    service: ProjectService = Depends(get_project_service),
) -> SuccessResponse[ProjectResponse]:
    """Create a new project in specified workspace."""
    project = await service.create_project(workspace_id, dto)
    return SuccessResponse(data=ProjectResponse.model_validate(project))
