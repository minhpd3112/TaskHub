from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.comment import Comment
from app.repositories.base import BaseRepository


class CommentRepository(BaseRepository[Comment]):
    """Repository handling database operations for Comment entities."""

    def __init__(self, db: AsyncSession) -> None:
        super().__init__(Comment, db)

    async def create_comment(self, task_id: UUID, author_id: UUID, content: str) -> Comment:
        """Create and persist a new comment, returning it with author relationship loaded."""
        comment = Comment(
            task_id=task_id,
            author_id=author_id,
            content=content,
        )
        self.db.add(comment)
        await self.db.flush()

        stmt = select(Comment).options(selectinload(Comment.author)).where(Comment.id == comment.id)
        result = await self.db.execute(stmt)
        return result.scalar_one()

    async def list_by_task(
        self,
        task_id: UUID,
        page: int = 1,
        limit: int = 50,
    ) -> tuple[list[Comment], int]:
        """List comments belonging to a task ordered by created_at ascending.

        Returns a tuple of (list_of_comments, total_count).
        """
        count_stmt = select(func.count(Comment.id)).where(Comment.task_id == task_id)
        total_result = await self.db.execute(count_stmt)
        total: int = total_result.scalar_one()

        offset = (page - 1) * limit
        stmt = (
            select(Comment)
            .options(selectinload(Comment.author))
            .where(Comment.task_id == task_id)
            .order_by(Comment.created_at.asc())
            .offset(offset)
            .limit(limit)
        )
        result = await self.db.execute(stmt)
        comments = list(result.scalars().all())

        return comments, total

    async def get_comment_by_id(self, comment_id: UUID) -> Comment | None:
        """Retrieve a single comment by its ID."""
        stmt = select(Comment).options(selectinload(Comment.author)).where(Comment.id == comment_id)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()
