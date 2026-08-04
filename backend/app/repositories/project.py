from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import ProjectStatus
from app.models.project import Project
from app.repositories.base import BaseRepository


class ProjectRepository(BaseRepository[Project]):
    """Repository handling database operations for Project entities."""

    def __init__(self, db: AsyncSession) -> None:
        super().__init__(Project, db)

    async def create_project(
        self,
        workspace_id: UUID,
        name: str,
        description: str | None = None,
        status: ProjectStatus = ProjectStatus.ACTIVE,
    ) -> Project:
        """Create and persist a new project within a workspace."""
        return await self.create(
            workspace_id=workspace_id,
            name=name,
            description=description,
            status=status,
        )

    async def get_by_workspace_and_name(
        self, workspace_id: UUID, name: str
    ) -> Project | None:
        """Find a project by workspace ID and name."""
        stmt = select(Project).where(
            Project.workspace_id == workspace_id,
            Project.name == name,
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()
