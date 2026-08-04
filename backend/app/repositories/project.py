from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import ProjectStatus
from app.models.project import Project
from app.models.task import Task
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

    async def get_by_workspace_and_name(self, workspace_id: UUID, name: str) -> Project | None:
        """Find a project by workspace ID and name."""
        stmt = select(Project).where(
            Project.workspace_id == workspace_id,
            Project.name == name,
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def list_by_workspace_with_task_count(
        self,
        workspace_id: UUID,
        status: ProjectStatus | None = None,
        skip: int = 0,
        limit: int = 20,
    ) -> tuple[list[tuple[Project, int]], int]:
        """List projects in a workspace with their associated task count."""
        count_stmt = select(func.count(Project.id)).where(Project.workspace_id == workspace_id)
        if status is not None:
            count_stmt = count_stmt.where(Project.status == status)
        total_result = await self.db.execute(count_stmt)
        total = total_result.scalar() or 0

        stmt = (
            select(Project, func.count(Task.id).label("task_count"))
            .outerjoin(Task, Task.project_id == Project.id)
            .where(Project.workspace_id == workspace_id)
        )
        if status is not None:
            stmt = stmt.where(Project.status == status)

        stmt = (
            stmt.group_by(Project.id).order_by(Project.created_at.desc()).offset(skip).limit(limit)
        )
        result = await self.db.execute(stmt)
        items = [(row[0], int(row[1])) for row in result.all()]
        return items, total

    async def get_detail_with_task_count(
        self,
        project_id: UUID,
    ) -> tuple[Project, int] | None:
        """Get project details including task count."""
        stmt = (
            select(Project, func.count(Task.id).label("task_count"))
            .outerjoin(Task, Task.project_id == Project.id)
            .where(Project.id == project_id)
            .group_by(Project.id)
        )
        result = await self.db.execute(stmt)
        row = result.first()
        if not row:
            return None
        return (row[0], int(row[1]))
