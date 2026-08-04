import logging
from uuid import UUID

from fastapi import BackgroundTasks
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ForbiddenError, NotFoundError, ValidationError
from app.models.enums import ProjectStatus, UserRole, WorkspaceRole
from app.models.task import Task
from app.models.user import User
from app.repositories.project import ProjectRepository
from app.repositories.task import TaskRepository
from app.repositories.workspace import WorkspaceRepository
from app.schemas.task import TaskCreateRequest
from app.services.email import EmailService

logger = logging.getLogger(__name__)


class TaskService:
    """Service handling business logic for Task management."""

    def __init__(
        self,
        db: AsyncSession,
        task_repo: TaskRepository | None = None,
        project_repo: ProjectRepository | None = None,
        workspace_repo: WorkspaceRepository | None = None,
        email_service: EmailService | None = None,
        redis: Redis | None = None,
    ) -> None:
        self.db = db
        self.task_repo = task_repo or TaskRepository(db)
        self.project_repo = project_repo or ProjectRepository(db)
        self.workspace_repo = workspace_repo or WorkspaceRepository(db)
        self.email_service = email_service or EmailService()
        self.redis = redis

    async def create_task(
        self,
        project_id: UUID,
        current_user: User,
        dto: TaskCreateRequest,
        background_tasks: BackgroundTasks | None = None,
    ) -> Task:
        """Create a new task within a project.

        Raises:
            NotFoundError: If project does not exist or current user is not a workspace member.
            ForbiddenError: If current user's role is VIEWER.
            ValidationError: If project is ARCHIVED or assignee_id is not a workspace member.
        """
        # 1. Check project existence & status
        project = await self.project_repo.get_by_id(project_id)
        if not project:
            raise NotFoundError("Project không tồn tại", code="NOT_FOUND")

        if project.status == ProjectStatus.ARCHIVED:
            raise ValidationError(
                "Không thể tạo công việc trong dự án đã bị lưu trữ (ARCHIVED).",
                code="PROJECT_ARCHIVED",
            )

        # 2. Check current user's workspace membership and RBAC permissions (IDOR Guard)
        if current_user.role != UserRole.ADMIN:
            member = await self.workspace_repo.get_member(project.workspace_id, current_user.id)
            if not member:
                raise NotFoundError("Project không tồn tại", code="NOT_FOUND")

            if member.role == WorkspaceRole.VIEWER:
                raise ForbiddenError(
                    "Bạn không có quyền tạo task trong project này",
                    code="FORBIDDEN",
                )

        # 3. Check assignee workspace membership
        assignee_member = await self.workspace_repo.get_member(
            project.workspace_id, dto.assignee_id
        )
        if not assignee_member:
            raise ValidationError(
                "Assignee phải là thành viên của workspace",
                code="INVALID_ASSIGNEE",
            )

        # 4. Create Task
        task = await self.task_repo.create_task(
            project_id=project_id,
            created_by=current_user.id,
            assignee_id=dto.assignee_id,
            title=dto.title,
            description=dto.description,
            status=dto.status,
            priority=dto.priority,
            due_date=dto.due_date,
        )

        # 5. Invalidate Redis Cache for project tasks list
        if self.redis:
            try:
                keys = await self.redis.keys(f"tasks:project:{project_id}:*")
                if keys:
                    await self.redis.delete(*keys)
            except Exception as exc:
                logger.warning(f"Failed to invalidate task list cache in Redis: {exc}")

        # 6. Dispatch async email notification for assignee
        if background_tasks and task.assignee and task.assignee.email:
            background_tasks.add_task(
                self.email_service.send_task_assignment_notification,
                assignee_email=task.assignee.email,
                task_title=task.title,
                assigner_name=current_user.full_name,
            )

        return task
