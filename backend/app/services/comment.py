from math import ceil
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.models.comment import Comment
from app.models.enums import UserRole
from app.models.user import User
from app.repositories.comment import CommentRepository
from app.repositories.task import TaskRepository
from app.repositories.workspace import WorkspaceRepository
from app.schemas.comment import CommentResponse
from app.schemas.common import PaginatedResponse, PaginationMeta


class CommentService:
    """Service handling business logic for Comment operations."""

    def __init__(
        self,
        db: AsyncSession,
        comment_repo: CommentRepository | None = None,
        task_repo: TaskRepository | None = None,
        workspace_repo: WorkspaceRepository | None = None,
    ) -> None:
        self.db = db
        self.comment_repo = comment_repo or CommentRepository(db)
        self.task_repo = task_repo or TaskRepository(db)
        self.workspace_repo = workspace_repo or WorkspaceRepository(db)

    async def create_comment(
        self,
        task_id: UUID,
        current_user: User,
        content: str,
    ) -> Comment:
        """Create a comment on a task.

        Raises:
            NotFoundError: If task does not exist or current user is not a workspace member.
        """
        task = await self.task_repo.get_task_detail(task_id)
        if not task:
            raise NotFoundError("Task không tồn tại", code="NOT_FOUND")

        if current_user.role != UserRole.ADMIN:
            member = await self.workspace_repo.get_member(
                task.project.workspace_id, current_user.id
            )
            if not member:
                raise NotFoundError("Task không tồn tại", code="NOT_FOUND")

        return await self.comment_repo.create_comment(
            task_id=task_id,
            author_id=current_user.id,
            content=content,
        )

    async def list_comments(
        self,
        task_id: UUID,
        current_user: User,
        page: int = 1,
        limit: int = 50,
    ) -> PaginatedResponse[CommentResponse]:
        """List comments for a task ordered by created_at ascending.

        Raises:
            NotFoundError: If task does not exist or current user is not a workspace member.
        """
        task = await self.task_repo.get_task_detail(task_id)
        if not task:
            raise NotFoundError("Task không tồn tại", code="NOT_FOUND")

        if current_user.role != UserRole.ADMIN:
            member = await self.workspace_repo.get_member(
                task.project.workspace_id, current_user.id
            )
            if not member:
                raise NotFoundError("Task không tồn tại", code="NOT_FOUND")

        comments, total = await self.comment_repo.list_by_task(
            task_id=task_id, page=page, limit=limit
        )

        total_pages = ceil(total / limit) if total > 0 else 0
        comment_responses = [CommentResponse.model_validate(c) for c in comments]

        return PaginatedResponse[CommentResponse](
            data=comment_responses,
            pagination=PaginationMeta(
                page=page,
                limit=limit,
                total=total,
                total_pages=total_pages,
            ),
        )
