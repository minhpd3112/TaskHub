from uuid import UUID

from sqlalchemy import select
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
