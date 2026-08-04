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

    async def list_projects(
        self,
        workspace_id: UUID,
        current_user_id: UUID,
        is_admin: bool = False,
        status: ProjectStatus | None = None,
        page: int = 1,
        limit: int = 20,
    ) -> tuple[list[tuple[Project, int]], int]:
        """List projects in a workspace with pagination and 404 Guard IDOR protection.

        Raises:
            NotFoundError: If workspace with workspace_id does not exist or user is not a member.
        """
        workspace = await self.workspace_repo.get_by_id(workspace_id)
        if not workspace:
            raise NotFoundError("Workspace không tồn tại", code="NOT_FOUND")

        if not is_admin:
            member = await self.workspace_repo.get_member(workspace_id, current_user_id)
            if not member:
                raise NotFoundError("Workspace không tồn tại", code="NOT_FOUND")

        skip = (page - 1) * limit
        return await self.project_repo.list_by_workspace_with_task_count(
            workspace_id=workspace_id,
            status=status,
            skip=skip,
            limit=limit,
        )

    async def get_project_detail(
        self,
        project_id: UUID,
        current_user_id: UUID,
        is_admin: bool = False,
    ) -> tuple[Project, int]:
        """Retrieve detail of a project with IDOR protection (404 Guard).

        Raises:
            NotFoundError: If project does not exist or user is not a member
                of the project's workspace.
        """
        result = await self.project_repo.get_detail_with_task_count(project_id)
        if not result:
            raise NotFoundError("Project không tồn tại", code="NOT_FOUND")

        project, task_count = result

        if not is_admin:
            member = await self.workspace_repo.get_member(project.workspace_id, current_user_id)
            if not member:
                raise NotFoundError("Project không tồn tại", code="NOT_FOUND")

        return project, task_count
