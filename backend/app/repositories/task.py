from datetime import date
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.enums import TaskPriority, TaskStatus
from app.models.task import Task
from app.repositories.base import BaseRepository


class TaskRepository(BaseRepository[Task]):
    """Repository handling database operations for Task entities."""

    def __init__(self, db: AsyncSession) -> None:
        super().__init__(Task, db)

    async def create_task(
        self,
        project_id: UUID,
        created_by: UUID,
        assignee_id: UUID,
        title: str,
        description: str | None = None,
        status: TaskStatus = TaskStatus.TODO,
        priority: TaskPriority = TaskPriority.MEDIUM,
        due_date: date | None = None,
    ) -> Task:
        """Create and persist a new task, returning it with assignee loaded."""
        task = Task(
            project_id=project_id,
            created_by=created_by,
            assignee_id=assignee_id,
            title=title,
            description=description,
            status=status,
            priority=priority,
            due_date=due_date,
        )
        self.db.add(task)
        await self.db.commit()

        # Load task with assignee and labels relationships
        stmt = (
            select(Task)
            .options(selectinload(Task.assignee), selectinload(Task.labels))
            .where(Task.id == task.id)
        )
        result = await self.db.execute(stmt)
        loaded_task = result.scalar_one()
        return loaded_task
