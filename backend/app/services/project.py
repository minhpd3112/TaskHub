from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.models.enums import ProjectStatus
from app.models.project import Project
from app.repositories.project import ProjectRepository
from app.repositories.workspace import WorkspaceRepository
from app.schemas.project import ProjectCreateRequest


class ProjectService:
    """Service handling business logic for Project management."""

    def __init__(
        self,
        db: AsyncSession,
        project_repo: ProjectRepository | None = None,
        workspace_repo: WorkspaceRepository | None = None,
    ) -> None:
        self.db = db
        self.project_repo = project_repo or ProjectRepository(db)
        self.workspace_repo = workspace_repo or WorkspaceRepository(db)

    async def create_project(
        self,
        workspace_id: UUID,
        dto: ProjectCreateRequest,
    ) -> Project:
        """Create a new project within a workspace.

        Raises:
            NotFoundError: If the workspace with workspace_id does not exist.
        """
        workspace = await self.workspace_repo.get_by_id(workspace_id)
        if not workspace:
            raise NotFoundError("Workspace không tồn tại", code="NOT_FOUND")

        project = await self.project_repo.create_project(
            workspace_id=workspace_id,
            name=dto.name,
            description=dto.description,
            status=ProjectStatus.ACTIVE,
        )
        return project
