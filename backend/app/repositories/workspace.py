from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import WorkspaceRole
from app.models.workspace import Workspace, WorkspaceMember
from app.repositories.base import BaseRepository


class WorkspaceRepository(BaseRepository[Workspace]):
    """Repository handling database operations for Workspace entities."""

    def __init__(self, db: AsyncSession) -> None:
        super().__init__(Workspace, db)

    async def create_workspace(self, name: str, owner_id: UUID) -> Workspace:
        """Create and persist a new workspace entity."""
        return await self.create(name=name, owner_id=owner_id)


class WorkspaceMemberRepository(BaseRepository[WorkspaceMember]):
    """Repository handling database operations for WorkspaceMember entities."""

    def __init__(self, db: AsyncSession) -> None:
        super().__init__(WorkspaceMember, db)

    async def add_member(
        self, workspace_id: UUID, user_id: UUID, role: WorkspaceRole
    ) -> WorkspaceMember:
        """Add a member to a workspace."""
        return await self.create(
            workspace_id=workspace_id,
            user_id=user_id,
            role=role,
        )
