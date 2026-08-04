from datetime import UTC, date, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.comment import Comment
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

    async def list_tasks_by_project(
        self,
        project_id: UUID,
        status: TaskStatus | None = None,
        priority: TaskPriority | None = None,
        assignee_id: UUID | None = None,
        due_date: date | None = None,
        editor_id: UUID | None = None,
        page: int = 1,
        limit: int = 20,
    ) -> tuple[list[Task], int]:
        """List tasks belonging to a project with filtering and pagination.

        Returns a tuple of (list_of_tasks, total_count).
        """
        conditions = [Task.project_id == project_id]

        if status is not None:
            conditions.append(Task.status == status)

        if priority is not None:
            conditions.append(Task.priority == priority)

        if assignee_id is not None:
            conditions.append(Task.assignee_id == assignee_id)

        if due_date is not None:
            conditions.append(Task.due_date == due_date)

        if editor_id is not None:
            conditions.append(Task.assignee_id == editor_id)

        # Count total items matching filters
        count_stmt = select(func.count(Task.id)).where(*conditions)
        total_result = await self.db.execute(count_stmt)
        total: int = total_result.scalar_one()

        # Query paginated tasks
        offset = (page - 1) * limit
        stmt = (
            select(Task)
            .options(selectinload(Task.assignee), selectinload(Task.labels))
            .where(*conditions)
            .order_by(Task.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        result = await self.db.execute(stmt)
        tasks = list(result.scalars().all())

        return tasks, total

    async def get_task_detail(self, task_id: UUID) -> Task | None:
        """Get a single task with all detailed relationships loaded."""
        stmt = (
            select(Task)
            .options(
                selectinload(Task.project),
                selectinload(Task.assignee),
                selectinload(Task.creator),
                selectinload(Task.labels),
                selectinload(Task.comments).selectinload(Comment.author),
            )
            .where(Task.id == task_id)
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def update_task(self, task_id: UUID, **data: Any) -> Task | None:
        """Update task attributes and return with all relationships eager-loaded."""
        task = await self.get_by_id(task_id)
        if not task:
            return None

        update_fields = {k: v for k, v in data.items() if v is not None}
        update_fields["updated_at"] = datetime.now(UTC)

        for key, value in update_fields.items():
            setattr(task, key, value)

        await self.db.commit()
        return await self.get_task_detail(task_id)

    async def update_status(self, task_id: UUID, status: TaskStatus) -> Task | None:
        """Update task status and return with eager-loaded relationships."""
        return await self.update_task(task_id, status=status)

    async def update_priority(self, task_id: UUID, priority: TaskPriority) -> Task | None:
        """Update task priority and return with eager-loaded relationships."""
        return await self.update_task(task_id, priority=priority)
