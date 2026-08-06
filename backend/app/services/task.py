import json
import logging
from datetime import date
from math import ceil
from uuid import UUID

from fastapi import BackgroundTasks
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import ForbiddenError, NotFoundError, ValidationError
from app.models.enums import ProjectStatus, TaskPriority, TaskStatus, UserRole, WorkspaceRole
from app.models.task import Task
from app.models.user import User
from app.repositories.project import ProjectRepository
from app.repositories.task import TaskRepository
from app.repositories.workspace import WorkspaceRepository
from app.schemas.common import PaginatedResponse, PaginationMeta
from app.schemas.task import TaskCreateRequest, TaskResponse, TaskUpdateRequest
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
            task_link = f"{settings.FRONTEND_URL}/tasks/{task.id}"
            background_tasks.add_task(
                self.email_service.send_task_assignment_notification,
                recipient_email=task.assignee.email,
                task_title=task.title,
                task_status=task.status.value,
                task_link=task_link,
                assigner_name=current_user.full_name,
            )

        return task

    async def list_tasks(
        self,
        project_id: UUID,
        current_user: User,
        status: TaskStatus | None = None,
        priority: TaskPriority | None = None,
        assignee_id: UUID | None = None,
        due_date: date | None = None,
        page: int = 1,
        limit: int = 20,
    ) -> PaginatedResponse[TaskResponse]:
        """List tasks for a project with filtering, pagination, RBAC scoping, and Redis caching.

        Raises:
            NotFoundError: If project does not exist or user is not a member (404 Guard).
        """
        # 1. Verify project existence
        project = await self.project_repo.get_by_id(project_id)
        if not project:
            raise NotFoundError("Project không tồn tại", code="NOT_FOUND")

        # 2. Workspace membership & RBAC check (IDOR Guard)
        role_str = "ADMIN"
        editor_id: UUID | None = None

        if current_user.role != UserRole.ADMIN:
            member = await self.workspace_repo.get_member(project.workspace_id, current_user.id)
            if not member:
                raise NotFoundError("Project không tồn tại", code="NOT_FOUND")

            role_str = member.role.value
            if member.role == WorkspaceRole.EDITOR:
                editor_id = current_user.id

        # 3. Redis Cache Lookup
        status_str = status.value if status else "all"
        priority_str = priority.value if priority else "all"
        assignee_str = str(assignee_id) if assignee_id else "all"
        due_date_str = due_date.isoformat() if due_date else "all"
        cache_key = (
            f"tasks:project:{project_id}:role:{role_str}:user:{current_user.id}:"
            f"p{page}:l{limit}:s{status_str}:pr{priority_str}:a{assignee_str}:d{due_date_str}"
        )

        if self.redis:
            try:
                cached_data = await self.redis.get(cache_key)
                if cached_data:
                    parsed = json.loads(cached_data)
                    return PaginatedResponse[TaskResponse].model_validate(parsed)
            except Exception as exc:
                logger.warning(f"Failed to fetch task list from Redis cache: {exc}")

        # 4. Database Query
        tasks, total = await self.task_repo.list_tasks_by_project(
            project_id=project_id,
            status=status,
            priority=priority,
            assignee_id=assignee_id,
            due_date=due_date,
            editor_id=editor_id,
            page=page,
            limit=limit,
        )

        total_pages = ceil(total / limit) if total > 0 else 0
        task_responses = [TaskResponse.model_validate(t) for t in tasks]
        paginated_response = PaginatedResponse[TaskResponse](
            data=task_responses,
            pagination=PaginationMeta(
                page=page,
                limit=limit,
                total=total,
                total_pages=total_pages,
            ),
        )

        # 5. Write to Redis Cache (TTL 300s)
        if self.redis:
            try:
                await self.redis.setex(
                    cache_key,
                    300,
                    json.dumps(paginated_response.model_dump(mode="json")),
                )
            except Exception as exc:
                logger.warning(f"Failed to set task list in Redis cache: {exc}")

        return paginated_response

    async def get_task_detail(
        self,
        task_id: UUID,
        current_user: User,
    ) -> Task:
        """Get detailed task information.

        Raises:
            NotFoundError: If task does not exist, user is not a workspace member,
                           or EDITOR tries to access a task not assigned to them (404 Guard).
        """
        task = await self.task_repo.get_task_detail(task_id)
        if not task:
            raise NotFoundError("Task không tồn tại", code="NOT_FOUND")

        # Workspace membership & RBAC check (IDOR Guard)
        if current_user.role != UserRole.ADMIN:
            member = await self.workspace_repo.get_member(
                task.project.workspace_id, current_user.id
            )
            if not member:
                raise NotFoundError("Task không tồn tại", code="NOT_FOUND")

            if member.role == WorkspaceRole.EDITOR and task.assignee_id != current_user.id:
                raise NotFoundError("Task không tồn tại", code="NOT_FOUND")

        return task

    async def update_task(
        self,
        task_id: UUID,
        current_user: User,
        data: TaskUpdateRequest,
    ) -> Task:
        """Update task information with full RBAC and business rules checks.

        Raises:
            NotFoundError: If task does not exist or current user is not a workspace member.
            ForbiddenError: If current user's role is not OWNER (or system ADMIN).
            ValidationError: If project is ARCHIVED or assignee_id is not a workspace member.
        """
        # 1. Fetch task with eager loaded project & workspace
        task = await self.task_repo.get_task_detail(task_id)
        if not task:
            raise NotFoundError("Task không tồn tại", code="NOT_FOUND")

        # 2. Check existence & IDOR Guard & RBAC Permissions
        if current_user.role != UserRole.ADMIN:
            member = await self.workspace_repo.get_member(
                task.project.workspace_id, current_user.id
            )
            if not member:
                raise NotFoundError("Task không tồn tại", code="NOT_FOUND")

            if member.role != WorkspaceRole.OWNER:
                raise ForbiddenError(
                    "Required role: OWNER",
                    code="FORBIDDEN",
                )

        # 3. Check project status (400 PROJECT_ARCHIVED)
        if task.project.status == ProjectStatus.ARCHIVED:
            raise ValidationError(
                "Cannot update task in an archived project",
                code="PROJECT_ARCHIVED",
            )

        # 4. Check new assignee if provided and changed
        if data.assignee_id is not None and data.assignee_id != task.assignee_id:
            assignee_member = await self.workspace_repo.get_member(
                task.project.workspace_id, data.assignee_id
            )
            if not assignee_member:
                raise ValidationError(
                    "Assignee must be a member of the workspace",
                    code="INVALID_ASSIGNEE",
                )

        # 5. Perform update in database
        update_dict = data.model_dump(exclude_unset=True)
        updated_task = await self.task_repo.update_task(task_id, **update_dict)
        if not updated_task:
            raise NotFoundError("Task không tồn tại", code="NOT_FOUND")

        # 6. Invalidate Redis Cache for project tasks list
        if self.redis:
            try:
                keys = await self.redis.keys(f"tasks:project:{task.project_id}:*")
                if keys:
                    await self.redis.delete(*keys)
            except Exception as exc:
                logger.warning(f"Failed to invalidate task list cache in Redis: {exc}")

        return updated_task

    async def update_task_status(
        self,
        task_id: UUID,
        status: TaskStatus,
        current_user: User,
    ) -> Task:
        """Update task status with RBAC enforcement and cache invalidation.

        Raises:
            NotFoundError: If task does not exist or user is not a workspace member (404 Guard).
            ForbiddenError: If EDITOR attempts to update status of task not assigned to them,
                            or if VIEWER attempts to update status.
            ValidationError: If project is ARCHIVED.
        """
        # 1. Fetch task detail
        task = await self.task_repo.get_task_detail(task_id)
        if not task:
            raise NotFoundError("Task không tồn tại", code="NOT_FOUND")

        # 2. Check existence & IDOR Guard & RBAC Permissions
        if current_user.role != UserRole.ADMIN:
            member = await self.workspace_repo.get_member(
                task.project.workspace_id, current_user.id
            )
            if not member:
                raise NotFoundError("Task không tồn tại", code="NOT_FOUND")

            if member.role == WorkspaceRole.VIEWER:
                raise ForbiddenError(
                    "Viewer không có quyền cập nhật trạng thái công việc",
                    code="FORBIDDEN",
                )

            if member.role == WorkspaceRole.EDITOR and task.assignee_id != current_user.id:
                raise ForbiddenError(
                    "Bạn không có quyền chuyển trạng thái công việc này",
                    code="FORBIDDEN",
                )

        # 3. Check project status (400 PROJECT_ARCHIVED)
        if task.project.status == ProjectStatus.ARCHIVED:
            raise ValidationError(
                "Không thể cập nhật công việc trong dự án đã bị archive",
                code="PROJECT_ARCHIVED",
            )

        # 4. Perform status update in database
        updated_task = await self.task_repo.update_status(task_id, status)
        if not updated_task:
            raise NotFoundError("Task không tồn tại", code="NOT_FOUND")

        # 5. Invalidate Redis Cache for project tasks list
        if self.redis:
            try:
                keys = await self.redis.keys(f"tasks:project:{task.project_id}:*")
                if keys:
                    await self.redis.delete(*keys)
            except Exception as exc:
                logger.warning(f"Failed to invalidate task list cache in Redis: {exc}")

        return updated_task

    async def update_task_priority(
        self,
        task_id: UUID,
        priority: TaskPriority,
        current_user: User,
    ) -> Task:
        """Update task priority with RBAC enforcement and cache invalidation.

        Raises:
            NotFoundError: If task does not exist or user is not a workspace member (404 Guard).
            ForbiddenError: If VIEWER attempts to update priority (unconditional),
                            or if EDITOR attempts to update priority of a task not assigned to them.
            ValidationError: If project is ARCHIVED.
        """
        # 1. Fetch task detail
        task = await self.task_repo.get_task_detail(task_id)
        if not task:
            raise NotFoundError("Task không tồn tại", code="NOT_FOUND")

        # 2. Check existence & IDOR Guard & RBAC Permissions
        if current_user.role != UserRole.ADMIN:
            member = await self.workspace_repo.get_member(
                task.project.workspace_id, current_user.id
            )
            if not member:
                raise NotFoundError("Task không tồn tại", code="NOT_FOUND")

            if member.role == WorkspaceRole.VIEWER:
                raise ForbiddenError(
                    "Viewer không có quyền cập nhật ưu tiên công việc",
                    code="FORBIDDEN",
                )

            if member.role == WorkspaceRole.EDITOR and task.assignee_id != current_user.id:
                raise ForbiddenError(
                    "Bạn không có quyền chuyển mức độ ưu tiên công việc này",
                    code="FORBIDDEN",
                )

        # 3. Check project status (400 PROJECT_ARCHIVED)
        if task.project.status == ProjectStatus.ARCHIVED:
            raise ValidationError(
                "Không thể cập nhật công việc trong dự án đã bị archive",
                code="PROJECT_ARCHIVED",
            )

        # 4. Perform priority update in database
        updated_task = await self.task_repo.update_priority(task_id, priority)
        if not updated_task:
            raise NotFoundError("Task không tồn tại", code="NOT_FOUND")

        # 5. Invalidate Redis Cache for project tasks list
        if self.redis:
            try:
                keys = await self.redis.keys(f"tasks:project:{task.project_id}:*")
                if keys:
                    await self.redis.delete(*keys)
            except Exception as exc:
                logger.warning(f"Failed to invalidate task list cache in Redis: {exc}")

        return updated_task
