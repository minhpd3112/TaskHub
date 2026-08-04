from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.workspace import Workspace, WorkspaceMember
from app.repositories.base import BaseRepository


class WorkspaceRepository(BaseRepository[Workspace]):
    """Repository handling database operations for Workspace entities."""

    def __init__(self, db: AsyncSession) -> None:
        super().__init__(Workspace, db)

    async def get_member(self, workspace_id: UUID, user_id: UUID) -> WorkspaceMember | None:
        """Retrieve workspace membership for a specific user."""
        stmt = select(WorkspaceMember).where(
            WorkspaceMember.workspace_id == workspace_id,
            WorkspaceMember.user_id == user_id,
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()
