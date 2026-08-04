import math
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user, require_workspace_role
from app.models.enums import ProjectStatus, UserRole, WorkspaceRole
from app.models.user import User
from app.models.workspace import WorkspaceMember
from app.schemas.common import PaginatedResponse, PaginationMeta, SuccessResponse
from app.schemas.project import (
    ProjectCreateRequest,
    ProjectListItemResponse,
    ProjectResponse,
)
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
        "Cho phép thành viên có vai trò EDITOR hoặc OWNER " "tạo một dự án mới trong Workspace."
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


@router.get(
    "/{workspace_id}/projects",
    response_model=PaginatedResponse[ProjectListItemResponse],
    status_code=status.HTTP_200_OK,
    summary="Danh sách dự án trong workspace",
    description="Xem danh sách dự án thuộc một Workspace kèm số lượng task.",
    operation_id="lietKeDuAn",
)
async def list_projects(
    workspace_id: UUID,
    status: ProjectStatus | None = None,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    service: ProjectService = Depends(get_project_service),
) -> PaginatedResponse[ProjectListItemResponse]:
    """List projects in workspace with pagination and optional status filtering."""
    items_with_counts, total = await service.list_projects(
        workspace_id=workspace_id,
        current_user_id=current_user.id,
        is_admin=(current_user.role == UserRole.ADMIN),
        status=status,
        page=page,
        limit=limit,
    )
    items = [
        ProjectListItemResponse(
            id=p.id,
            workspace_id=p.workspace_id,
            name=p.name,
            description=p.description,
            status=p.status,
            task_count=cnt,
            created_at=p.created_at,
            updated_at=p.updated_at,
        )
        for p, cnt in items_with_counts
    ]
    total_pages = math.ceil(total / limit) if total > 0 else 0
    return PaginatedResponse(
        data=items,
        pagination=PaginationMeta(
            page=page,
            limit=limit,
            total=total,
            total_pages=total_pages,
        ),
    )
