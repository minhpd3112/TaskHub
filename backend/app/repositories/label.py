from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.label import Label
from app.repositories.base import BaseRepository


class LabelRepository(BaseRepository[Label]):
    """Repository handling database operations for Label entities."""

    def __init__(self, db: AsyncSession) -> None:
        super().__init__(Label, db)

    async def get_by_project_and_name(self, project_id: UUID, name: str) -> Label | None:
        """Find a label by project ID and name."""
        stmt = select(Label).where(
            Label.project_id == project_id,
            Label.name == name,
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def list_by_project(self, project_id: UUID) -> list[Label]:
        """List all labels in a project sorted by name ascending."""
        stmt = select(Label).where(Label.project_id == project_id).order_by(Label.name.asc())
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def create_label(self, project_id: UUID, name: str, color: str) -> Label:
        """Create and persist a new label within a project."""
        return await self.create(
            project_id=project_id,
            name=name,
            color=color,
        )
