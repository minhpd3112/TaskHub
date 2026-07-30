from typing import Any, Generic, TypeVar
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

ModelType = TypeVar("ModelType")


class BaseRepository(Generic[ModelType]):
    """Generic async repository providing CRUD operations for SQLAlchemy models."""

    def __init__(self, model: type[ModelType], db: AsyncSession) -> None:
        self.model = model
        self.db = db

    async def get_by_id(self, id: UUID) -> ModelType | None:
        """Retrieve a single entity by its primary key ID."""
        id_attr = getattr(self.model, "id")  # noqa: B009
        stmt = select(self.model).where(id_attr == id)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_all(self, *, skip: int = 0, limit: int = 20) -> list[ModelType]:
        """Retrieve a list of entities with pagination."""
        stmt = select(self.model).offset(skip).limit(limit)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def count(self, *filters: Any) -> int:
        """Count total entities matching optional filter conditions."""
        stmt = select(func.count()).select_from(self.model)
        if filters:
            stmt = stmt.where(*filters)
        result = await self.db.execute(stmt)
        count_val = result.scalar_one_or_none()
        return count_val if count_val is not None else 0

    async def create(self, **data: Any) -> ModelType:
        """Create and persist a new entity instance."""
        instance = self.model(**data)
        self.db.add(instance)
        await self.db.flush()
        await self.db.refresh(instance)
        return instance

    async def update_by_id(self, id: UUID, **data: Any) -> ModelType | None:
        """Update an existing entity by its ID."""
        instance = await self.get_by_id(id)
        if not instance:
            return None
        for key, value in data.items():
            if hasattr(instance, key):
                setattr(instance, key, value)
        await self.db.flush()
        await self.db.refresh(instance)
        return instance

    async def delete_by_id(self, id: UUID) -> bool:
        """Delete an entity by its ID."""
        instance = await self.get_by_id(id)
        if not instance:
            return False
        await self.db.delete(instance)
        await self.db.flush()
        return True
