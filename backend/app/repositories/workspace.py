from uuid import UUID

from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import WorkspaceRole
from app.models.project import Project
from app.models.task import Task
from app.models.user import User
from app.models.workspace import Workspace, WorkspaceMember
from app.repositories.base import BaseRepository


class WorkspaceRepository(BaseRepository[Workspace]):
    """Repository handling database operations for Workspace entities."""

    def __init__(self, db: AsyncSession) -> None:
        super().__init__(Workspace, db)

    async def create_workspace(self, name: str, owner_id: UUID) -> Workspace:
        """Create and persist a new workspace entity."""
        return await self.create(name=name, owner_id=owner_id)

    async def get_workspaces_by_user_id(
        self, user_id: UUID
    ) -> list[tuple[Workspace, WorkspaceRole]]:
        """Retrieve all workspaces where user is a member, alongside their role."""
        stmt = (
            select(Workspace, WorkspaceMember.role)
            .join(WorkspaceMember, Workspace.id == WorkspaceMember.workspace_id)
            .where(WorkspaceMember.user_id == user_id)
            .order_by(Workspace.created_at.desc())
        )
        result = await self.db.execute(stmt)
        return [(row[0], row[1]) for row in result.all()]


class WorkspaceMemberRepository(BaseRepository[WorkspaceMember]):
    """Repository handling database operations for WorkspaceMember entities."""

    def __init__(self, db: AsyncSession) -> None:
        super().__init__(WorkspaceMember, db)

    async def add_member(
        self, workspace_id: UUID, user_id: UUID, role: WorkspaceRole
    ) -> WorkspaceMember:
        """Add a member to a workspace."""
        return await self.create(
            workspace_id=workspace_id,
            user_id=user_id,
            role=role,
        )

    async def get_member(self, workspace_id: UUID, user_id: UUID) -> WorkspaceMember | None:
        """Get a workspace member by workspace ID and user ID."""
        stmt = select(WorkspaceMember).where(
            WorkspaceMember.workspace_id == workspace_id,
            WorkspaceMember.user_id == user_id,
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def list_members_with_user_details(
        self, workspace_id: UUID
    ) -> list[tuple[WorkspaceMember, User]]:
        """Retrieve all members of a workspace alongside User details."""
        stmt = (
            select(WorkspaceMember, User)
            .join(User, WorkspaceMember.user_id == User.id)
            .where(WorkspaceMember.workspace_id == workspace_id)
            .order_by(WorkspaceMember.joined_at.asc())
        )
        result = await self.db.execute(stmt)
        return [(row[0], row[1]) for row in result.all()]

    async def count_owners(self, workspace_id: UUID) -> int:
        """Count the number of OWNER members in a workspace."""
        stmt = (
            select(func.count())
            .select_from(WorkspaceMember)
            .where(
                WorkspaceMember.workspace_id == workspace_id,
                WorkspaceMember.role == WorkspaceRole.OWNER,
            )
        )
        result = await self.db.execute(stmt)
        return result.scalar_one() or 0

    async def update_role(
        self, workspace_id: UUID, user_id: UUID, new_role: WorkspaceRole
    ) -> WorkspaceMember | None:
        """Update the role of a workspace member."""
        member = await self.get_member(workspace_id, user_id)
        if member:
            member.role = new_role
            await self.db.flush()
        return member

    async def remove_member(self, workspace_id: UUID, user_id: UUID) -> None:
        """Remove a member record from workspace_members."""
        stmt = delete(WorkspaceMember).where(
            WorkspaceMember.workspace_id == workspace_id,
            WorkspaceMember.user_id == user_id,
        )
        await self.db.execute(stmt)

    async def reassign_workspace_member_tasks(
        self, workspace_id: UUID, member_id: UUID, new_assignee_id: UUID
    ) -> int:
        """Reassign member's tasks across projects in workspace to new_assignee_id."""
        project_ids_subquery = select(Project.id).where(Project.workspace_id == workspace_id)
        stmt = (
            update(Task)
            .where(
                Task.assignee_id == member_id,
                Task.project_id.in_(project_ids_subquery),
            )
            .values(assignee_id=new_assignee_id)
        )
        res = await self.db.execute(stmt)
        return res.rowcount or 0
