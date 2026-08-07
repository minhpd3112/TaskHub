import logging
from uuid import UUID

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, ForbiddenError, NotFoundError, ValidationError
from app.models.enums import WorkspaceRole
from app.models.label import Label, TaskLabel
from app.models.project import Project
from app.models.task import Task
from app.models.workspace import WorkspaceMember
from app.repositories.label import LabelRepository
from app.repositories.project import ProjectRepository
from app.repositories.task import TaskRepository
from app.repositories.workspace import WorkspaceRepository
from app.schemas.label import LabelCreateRequest

logger = logging.getLogger(__name__)


class LabelService:
    """Service handling business logic for Label management."""

    def __init__(
        self,
        db: AsyncSession,
        label_repo: LabelRepository | None = None,
        project_repo: ProjectRepository | None = None,
        workspace_repo: WorkspaceRepository | None = None,
        task_repo: TaskRepository | None = None,
        redis: Redis | None = None,
    ) -> None:
        self.db = db
        self.label_repo = label_repo or LabelRepository(db)
        self.project_repo = project_repo or ProjectRepository(db)
        self.workspace_repo = workspace_repo or WorkspaceRepository(db)
        self.task_repo = task_repo or TaskRepository(db)
        self.redis = redis

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

    async def _get_task_with_access(
        self,
        task_id: UUID,
        current_user_id: UUID,
        is_admin: bool = False,
    ) -> tuple[Task, WorkspaceMember | None]:
        """Verify task existence and workspace membership (IDOR protection 404 Guard).

        Raises:
            NotFoundError: If task does not exist or user is not a workspace member.
        """
        task = await self.task_repo.get_task_detail(task_id)
        if not task:
            raise NotFoundError("Công việc không tồn tại", code="NOT_FOUND")

        member: WorkspaceMember | None = None
        if not is_admin:
            member = await self.workspace_repo.get_member(
                task.project.workspace_id, current_user_id
            )
            if member is None:
                raise NotFoundError("Công việc không tồn tại", code="NOT_FOUND")

        return task, member

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
            ForbiddenError: If member's role is not OWNER (ADR-006).
            ConflictError: If a label with the same name already exists in the project.
        """
        _project, member = await self._get_project_with_access(
            project_id=project_id,
            current_user_id=current_user_id,
            is_admin=is_admin,
        )

        if not is_admin and member is not None and member.role != WorkspaceRole.OWNER:
            raise ForbiddenError("Chỉ OWNER mới có quyền tạo nhãn", code="FORBIDDEN")

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

    async def assign_label(
        self,
        task_id: UUID,
        label_id: UUID,
        current_user_id: UUID,
        is_admin: bool = False,
    ) -> tuple[TaskLabel, Label]:
        """Assign a label to a task.

        Raises:
            NotFoundError: If task or label does not exist, or user is non-member (IDOR Guard).
            ForbiddenError: If member's role is not OWNER (ADR-006).
            ValidationError: If label belongs to a different project.
        """
        task, member = await self._get_task_with_access(
            task_id=task_id,
            current_user_id=current_user_id,
            is_admin=is_admin,
        )

        if not is_admin and member is not None and member.role != WorkspaceRole.OWNER:
            raise ForbiddenError("Chỉ OWNER mới có quyền gán nhãn", code="FORBIDDEN")

        label = await self.label_repo.get_by_id(label_id)
        if not label:
            raise NotFoundError("Nhãn không tồn tại", code="NOT_FOUND")

        if label.project_id != task.project_id:
            raise ValidationError(
                "Nhãn không thuộc dự án của công việc",
                code="LABEL_NOT_IN_PROJECT",
            )

        existing_task_label = await self.label_repo.get_task_label(task_id, label_id)
        if existing_task_label:
            return existing_task_label, label

        task_label = await self.label_repo.assign_label_to_task(task_id, label_id)

        # Invalidate Redis Cache for project tasks list
        if self.redis:
            try:
                keys = await self.redis.keys(f"tasks:project:{task.project_id}:*")
                if keys:
                    await self.redis.delete(*keys)
            except Exception as exc:
                logger.warning(f"Failed to invalidate task list cache in Redis: {exc}")

        return task_label, label

    async def remove_label(
        self,
        task_id: UUID,
        label_id: UUID,
        current_user_id: UUID,
        is_admin: bool = False,
    ) -> None:
        """Remove a label from a task.

        Raises:
            NotFoundError: If task or label does not exist, or user is non-member (IDOR Guard).
            ForbiddenError: If member's role is not OWNER (ADR-006).
            ValidationError: If label belongs to a different project.
        """
        task, member = await self._get_task_with_access(
            task_id=task_id,
            current_user_id=current_user_id,
            is_admin=is_admin,
        )

        if not is_admin and member is not None and member.role != WorkspaceRole.OWNER:
            raise ForbiddenError("Chỉ OWNER mới có quyền gỡ nhãn", code="FORBIDDEN")

        label = await self.label_repo.get_by_id(label_id)
        if not label:
            raise NotFoundError("Nhãn không tồn tại", code="NOT_FOUND")

        if label.project_id != task.project_id:
            raise ValidationError(
                "Nhãn không thuộc dự án của công việc",
                code="LABEL_NOT_IN_PROJECT",
            )

        await self.label_repo.remove_label_from_task(task_id, label_id)

        # Invalidate Redis Cache for project tasks list
        if self.redis:
            try:
                keys = await self.redis.keys(f"tasks:project:{task.project_id}:*")
                if keys:
                    await self.redis.delete(*keys)
            except Exception as exc:
                logger.warning(f"Failed to invalidate task list cache in Redis: {exc}")
