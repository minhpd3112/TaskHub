from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.schemas.common import SuccessResponse
from app.schemas.workspace import (
    UserWorkspaceResponse,
    WorkspaceCreateRequest,
    WorkspaceResponse,
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
