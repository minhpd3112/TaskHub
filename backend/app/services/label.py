from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, ForbiddenError, NotFoundError
from app.models.enums import WorkspaceRole
from app.models.label import Label
from app.models.project import Project
from app.models.workspace import WorkspaceMember
from app.repositories.label import LabelRepository
from app.repositories.project import ProjectRepository
from app.repositories.workspace import WorkspaceRepository
from app.schemas.label import LabelCreateRequest


class LabelService:
    """Service handling business logic for Label management."""

    def __init__(
        self,
        db: AsyncSession,
        label_repo: LabelRepository | None = None,
        project_repo: ProjectRepository | None = None,
        workspace_repo: WorkspaceRepository | None = None,
    ) -> None:
        self.db = db
        self.label_repo = label_repo or LabelRepository(db)
        self.project_repo = project_repo or ProjectRepository(db)
        self.workspace_repo = workspace_repo or WorkspaceRepository(db)

    async def _get_project_with_access(
        self,
        project_id: UUID,
        current_user_id: UUID,
        is_admin: bool = False,
    ) -> tuple[Project, WorkspaceMember | None]:
        """Verify project existence and workspace membership (IDOR protection 404 Guard).

        Raises:
            NotFoundError: If project does not exist or user is not a workspace member.
        """
        project = await self.project_repo.get_by_id(project_id)
        if not project:
            raise NotFoundError("Project không tồn tại", code="NOT_FOUND")

        member: WorkspaceMember | None = None
        if not is_admin:
            member = await self.workspace_repo.get_member(project.workspace_id, current_user_id)
            if member is None:
                raise NotFoundError("Project không tồn tại", code="NOT_FOUND")

        return project, member

    async def create_label(
        self,
        project_id: UUID,
        dto: LabelCreateRequest,
        current_user_id: UUID,
        is_admin: bool = False,
    ) -> Label:
        """Create a new label in a project.

        Raises:
            NotFoundError: If project does not exist or user is non-member (IDOR Guard).
            ForbiddenError: If member's role is VIEWER.
            ConflictError: If a label with the same name already exists in the project.
        """
        _project, member = await self._get_project_with_access(
            project_id=project_id,
            current_user_id=current_user_id,
            is_admin=is_admin,
        )

        if not is_admin and member is not None and member.role == WorkspaceRole.VIEWER:
            raise ForbiddenError("Chỉ OWNER hoặc EDITOR mới có quyền tạo nhãn", code="FORBIDDEN")

        existing = await self.label_repo.get_by_project_and_name(project_id, dto.name)
        if existing:
            raise ConflictError(
                f"Nhãn '{dto.name}' đã tồn tại trong dự án này",
                code="CONFLICT",
            )

        return await self.label_repo.create_label(
            project_id=project_id,
            name=dto.name,
            color=dto.color,
        )

    async def list_labels(
        self,
        project_id: UUID,
        current_user_id: UUID,
        is_admin: bool = False,
    ) -> list[Label]:
        """List all labels in a project.

        Raises:
            NotFoundError: If project does not exist or user is non-member (IDOR Guard).
        """
        await self._get_project_with_access(
            project_id=project_id,
            current_user_id=current_user_id,
            is_admin=is_admin,
        )
        return await self.label_repo.list_by_project(project_id)
