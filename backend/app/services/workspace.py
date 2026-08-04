from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import WorkspaceRole
from app.models.user import User
from app.repositories.workspace import WorkspaceMemberRepository, WorkspaceRepository
from app.schemas.workspace import (
    UserWorkspaceResponse,
    WorkspaceCreateRequest,
    WorkspaceResponse,
)


class WorkspaceService:
    """Service handling workspace business logic."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.workspace_repo = WorkspaceRepository(db)
        self.workspace_member_repo = WorkspaceMemberRepository(db)

    async def create_workspace(
        self, current_user: User, dto: WorkspaceCreateRequest
    ) -> WorkspaceResponse:
        """Create a new workspace and assign current user as OWNER."""
        workspace = await self.workspace_repo.create_workspace(
            name=dto.name,
            owner_id=current_user.id,
        )
        await self.workspace_member_repo.add_member(
            workspace_id=workspace.id,
            user_id=current_user.id,
            role=WorkspaceRole.OWNER,
        )
        await self.db.commit()
        await self.db.refresh(workspace)
        return WorkspaceResponse.model_validate(workspace)

    async def get_user_workspaces(self, current_user: User) -> list[UserWorkspaceResponse]:
        """Retrieve all workspaces where the current user is a member, including their role."""
        items = await self.workspace_repo.get_workspaces_by_user_id(current_user.id)
        return [
            UserWorkspaceResponse(
                id=workspace.id,
                name=workspace.name,
                owner_id=workspace.owner_id,
                role=role,
                created_at=workspace.created_at,
            )
            for workspace, role in items
        ]
