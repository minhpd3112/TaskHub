from uuid import UUID

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.schemas.common import SuccessResponse
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
from app.services.workspace import WorkspaceService

router = APIRouter()


def get_workspace_service(
    db: AsyncSession = Depends(get_db),
) -> WorkspaceService:
    """Dependency providing WorkspaceService instance."""
    return WorkspaceService(db=db)


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
