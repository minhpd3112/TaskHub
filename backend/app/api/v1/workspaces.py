import math
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response, status
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
from app.schemas.workspace import (
    MemberInviteRequest,
    MemberUpdateRoleRequest,
    UserWorkspaceResponse,
    WorkspaceCreateRequest,
    WorkspaceMemberDetailResponse,
    WorkspaceMemberResponse,
    WorkspaceResponse,
    WorkspaceUpdateRequest,
)
from app.services.project import ProjectService
from app.services.workspace import WorkspaceService

router = APIRouter()


def get_workspace_service(
    db: AsyncSession = Depends(get_db),
) -> WorkspaceService:
    """Dependency providing WorkspaceService instance."""
    return WorkspaceService(db=db)


def get_project_service(
    db: AsyncSession = Depends(get_db),
) -> ProjectService:
    """Dependency providing ProjectService instance."""
    return ProjectService(db=db)


@router.post(
    "",
    response_model=SuccessResponse[WorkspaceResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Create a new workspace",
)
async def create_workspace(
    dto: WorkspaceCreateRequest,
    current_user: User = Depends(get_current_user),
    service: WorkspaceService = Depends(get_workspace_service),
) -> SuccessResponse[WorkspaceResponse]:
    """Create a new workspace for the authenticated user and assign them as OWNER."""
    workspace = await service.create_workspace(current_user, dto)
    return SuccessResponse(data=workspace)


@router.get(
    "",
    response_model=SuccessResponse[list[UserWorkspaceResponse]],
    status_code=status.HTTP_200_OK,
    summary="List my workspaces",
    operation_id="lietKeWorkspaceCuaToi",
)
async def list_my_workspaces(
    current_user: User = Depends(get_current_user),
    service: WorkspaceService = Depends(get_workspace_service),
) -> SuccessResponse[list[UserWorkspaceResponse]]:
    """Retrieve all workspaces where the authenticated user is a member."""
    workspaces = await service.get_user_workspaces(current_user)
    return SuccessResponse(data=workspaces)


@router.post(
    "/{workspace_id}/members",
    response_model=SuccessResponse[WorkspaceMemberResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Invite member to workspace",
    operation_id="themThanhVien",
)
async def invite_member(
    workspace_id: UUID,
    dto: MemberInviteRequest,
    current_user: User = Depends(get_current_user),
    service: WorkspaceService = Depends(get_workspace_service),
) -> SuccessResponse[WorkspaceMemberResponse]:
    """Invite a new member to the workspace."""
    member = await service.invite_member(current_user, workspace_id, dto)
    return SuccessResponse(data=member)


@router.get(
    "/{workspace_id}/members",
    response_model=SuccessResponse[list[WorkspaceMemberDetailResponse]],
    status_code=status.HTTP_200_OK,
    summary="List workspace members",
    operation_id="lietKeThanhVien",
)
async def list_workspace_members(
    workspace_id: UUID,
    current_user: User = Depends(get_current_user),
    service: WorkspaceService = Depends(get_workspace_service),
) -> SuccessResponse[list[WorkspaceMemberDetailResponse]]:
    """Retrieve all members of a workspace."""
    members = await service.list_workspace_members(current_user, workspace_id)
    return SuccessResponse(data=members)


@router.patch(
    "/{workspace_id}/members/{user_id}",
    response_model=SuccessResponse[WorkspaceMemberResponse],
    status_code=status.HTTP_200_OK,
    summary="Update workspace member role",
    operation_id="capNhatVaiTroThanhVien",
)
async def update_member_role(
    workspace_id: UUID,
    user_id: UUID,
    dto: MemberUpdateRoleRequest,
    current_user: User = Depends(get_current_user),
    service: WorkspaceService = Depends(get_workspace_service),
) -> SuccessResponse[WorkspaceMemberResponse]:
    """Update role of an existing workspace member."""
    member = await service.update_member_role(current_user, workspace_id, user_id, dto)
    return SuccessResponse(data=member)


@router.delete(
    "/{workspace_id}/members/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove workspace member",
    operation_id="xoaThanhVien",
)
async def remove_member(
    workspace_id: UUID,
    user_id: UUID,
    current_user: User = Depends(get_current_user),
    service: WorkspaceService = Depends(get_workspace_service),
) -> Response:
    """Remove a member from the workspace."""
    await service.remove_member(current_user, workspace_id, user_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/{workspace_id}/projects",
    response_model=SuccessResponse[ProjectResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Tạo project mới trong workspace",
    description=("Cho phép thành viên có vai trò OWNER tạo một dự án mới trong Workspace."),
    operation_id="taoDuAn",
)
async def create_project(
    workspace_id: UUID,
    dto: ProjectCreateRequest,
    member: WorkspaceMember = Depends(require_workspace_role(WorkspaceRole.OWNER)),
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


@router.get(
    "/{workspace_id}",
    response_model=SuccessResponse[WorkspaceResponse],
    status_code=status.HTTP_200_OK,
    summary="Get workspace details",
    operation_id="xemWorkspace",
)
async def get_workspace(
    workspace_id: UUID,
    current_user: User = Depends(get_current_user),
    service: WorkspaceService = Depends(get_workspace_service),
) -> SuccessResponse[WorkspaceResponse]:
    """Retrieve details of a single workspace by ID."""
    workspace = await service.get_workspace_by_id(current_user, workspace_id)
    return SuccessResponse(data=workspace)


@router.patch(
    "/{workspace_id}",
    response_model=SuccessResponse[WorkspaceResponse],
    status_code=status.HTTP_200_OK,
    summary="Update workspace",
    operation_id="capNhatWorkspace",
)
async def update_workspace(
    workspace_id: UUID,
    dto: WorkspaceUpdateRequest,
    current_user: User = Depends(get_current_user),
    service: WorkspaceService = Depends(get_workspace_service),
) -> SuccessResponse[WorkspaceResponse]:
    """Update workspace name."""
    workspace = await service.update_workspace(current_user, workspace_id, dto)
    return SuccessResponse(data=workspace)


@router.delete(
    "/{workspace_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete workspace",
    operation_id="xoaWorkspace",
)
async def delete_workspace(
    workspace_id: UUID,
    current_user: User = Depends(get_current_user),
    service: WorkspaceService = Depends(get_workspace_service),
) -> Response:
    """Delete workspace."""
    await service.delete_workspace(current_user, workspace_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
