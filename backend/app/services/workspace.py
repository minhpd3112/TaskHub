from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    ConflictError,
    ForbiddenError,
    NotFoundError,
    ValidationError,
)
from app.models.enums import UserRole, WorkspaceRole
from app.models.user import User
from app.repositories.user import UserRepository
from app.repositories.workspace import WorkspaceMemberRepository, WorkspaceRepository
from app.schemas.workspace import (
    MemberInviteRequest,
    MemberUpdateRoleRequest,
    UserWorkspaceResponse,
    WorkspaceCreateRequest,
    WorkspaceMemberDetailResponse,
    WorkspaceMemberResponse,
    WorkspaceResponse,
    WorkspaceUpdateRequest,
)


class WorkspaceService:
    """Service handling workspace business logic."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.workspace_repo = WorkspaceRepository(db)
        self.workspace_member_repo = WorkspaceMemberRepository(db)
        self.user_repo = UserRepository(db)

    async def create_workspace(
        self, current_user: User, dto: WorkspaceCreateRequest
    ) -> WorkspaceResponse:
        """Create a new workspace and assign current user as OWNER."""
        workspace = await self.workspace_repo.create_workspace(
            name=dto.name,
            owner_id=current_user.id,
        )
        await self.workspace_member_repo.add_member(
            workspace_id=workspace.id,
            user_id=current_user.id,
            role=WorkspaceRole.OWNER,
        )
        await self.db.commit()
        await self.db.refresh(workspace)
        return WorkspaceResponse.model_validate(workspace)

    async def get_user_workspaces(self, current_user: User) -> list[UserWorkspaceResponse]:
        """Retrieve all workspaces where the current user is a member, including their role."""
        items = await self.workspace_repo.get_workspaces_by_user_id(current_user.id)
        return [
            UserWorkspaceResponse(
                id=workspace.id,
                name=workspace.name,
                owner_id=workspace.owner_id,
                role=role,
                created_at=workspace.created_at,
            )
            for workspace, role in items
        ]

    async def get_workspace_by_id(
        self, current_user: User, workspace_id: UUID
    ) -> WorkspaceResponse:
        """Retrieve workspace details by ID if user is a member or System ADMIN."""
        workspace = await self.workspace_repo.get_by_id(workspace_id)
        if not workspace:
            raise NotFoundError("Workspace not found.", code="NOT_FOUND")

        if current_user.role != UserRole.ADMIN:
            member = await self.workspace_member_repo.get_member(workspace_id, current_user.id)
            if not member:
                raise ForbiddenError("Not a member of this workspace.", code="FORBIDDEN")

        return WorkspaceResponse.model_validate(workspace)

    async def invite_member(
        self, current_user: User, workspace_id: UUID, dto: MemberInviteRequest
    ) -> WorkspaceMemberResponse:
        """Invite a new member to the workspace."""
        workspace = await self.workspace_repo.get_by_id(workspace_id)
        if not workspace:
            raise NotFoundError("Workspace not found.", code="NOT_FOUND")

        if current_user.role != UserRole.ADMIN:
            caller_member = await self.workspace_member_repo.get_member(
                workspace_id, current_user.id
            )
            if not caller_member or caller_member.role != WorkspaceRole.OWNER:
                raise ForbiddenError(
                    "Only workspace OWNER or system ADMIN can invite members.", code="FORBIDDEN"
                )

        target_user = await self.user_repo.get_by_email(dto.email)
        if not target_user:
            raise NotFoundError("User with this email not found.", code="USER_NOT_FOUND")

        existing_member = await self.workspace_member_repo.get_member(workspace_id, target_user.id)
        if existing_member:
            raise ConflictError(
                "User is already a member of this workspace.", code="ALREADY_MEMBER"
            )

        new_member = await self.workspace_member_repo.add_member(
            workspace_id=workspace_id,
            user_id=target_user.id,
            role=dto.role,
        )
        await self.db.commit()
        await self.db.refresh(new_member)
        return WorkspaceMemberResponse.model_validate(new_member)

    async def update_member_role(
        self,
        current_user: User,
        workspace_id: UUID,
        target_user_id: UUID,
        dto: MemberUpdateRoleRequest,
    ) -> WorkspaceMemberResponse:
        """Update role of an existing workspace member."""
        workspace = await self.workspace_repo.get_by_id(workspace_id)
        if not workspace:
            raise NotFoundError("Workspace not found.", code="NOT_FOUND")

        if current_user.role != UserRole.ADMIN:
            caller_member = await self.workspace_member_repo.get_member(
                workspace_id, current_user.id
            )
            if not caller_member or caller_member.role != WorkspaceRole.OWNER:
                raise ForbiddenError(
                    "Only workspace OWNER or system ADMIN can update member roles.",
                    code="FORBIDDEN",
                )

        target_member = await self.workspace_member_repo.get_member(workspace_id, target_user_id)
        if not target_member:
            raise NotFoundError("Workspace member not found.", code="MEMBER_NOT_FOUND")

        if target_member.role == WorkspaceRole.OWNER and dto.role != WorkspaceRole.OWNER:
            owner_count = await self.workspace_member_repo.count_owners(workspace_id)
            if owner_count <= 1:
                raise ValidationError(
                    "Cannot demote the last owner of the workspace.",
                    code="CANNOT_DEMOTE_LAST_OWNER",
                )

        updated_member = await self.workspace_member_repo.update_role(
            workspace_id, target_user_id, dto.role
        )
        await self.db.commit()
        if updated_member:
            await self.db.refresh(updated_member)
        return WorkspaceMemberResponse.model_validate(updated_member)

    async def remove_member(
        self, current_user: User, workspace_id: UUID, target_user_id: UUID
    ) -> None:
        """Remove a member from the workspace and reassign active tasks to workspace owner."""
        workspace = await self.workspace_repo.get_by_id(workspace_id)
        if not workspace:
            raise NotFoundError("Workspace not found.", code="NOT_FOUND")

        if current_user.role != UserRole.ADMIN:
            caller_member = await self.workspace_member_repo.get_member(
                workspace_id, current_user.id
            )
            if not caller_member or caller_member.role != WorkspaceRole.OWNER:
                raise ForbiddenError(
                    "Only workspace OWNER or system ADMIN can remove members.", code="FORBIDDEN"
                )

        target_member = await self.workspace_member_repo.get_member(workspace_id, target_user_id)
        if not target_member:
            raise NotFoundError("Workspace member not found.", code="MEMBER_NOT_FOUND")

        if target_member.role == WorkspaceRole.OWNER:
            owner_count = await self.workspace_member_repo.count_owners(workspace_id)
            if owner_count <= 1:
                raise ValidationError(
                    "Cannot remove the last owner of the workspace.",
                    code="CANNOT_REMOVE_OWNER",
                )

        await self.workspace_member_repo.reassign_workspace_member_tasks(
            workspace_id=workspace_id,
            member_id=target_user_id,
            new_assignee_id=workspace.owner_id,
        )
        await self.workspace_member_repo.remove_member(workspace_id, target_user_id)
        await self.db.commit()

    async def list_workspace_members(
        self, current_user: User, workspace_id: UUID
    ) -> list[WorkspaceMemberDetailResponse]:
        """List all members of a workspace alongside user details."""
        workspace = await self.workspace_repo.get_by_id(workspace_id)
        if not workspace:
            raise NotFoundError("Workspace not found.", code="NOT_FOUND")

        if current_user.role != UserRole.ADMIN:
            caller_member = await self.workspace_member_repo.get_member(
                workspace_id, current_user.id
            )
            if not caller_member:
                raise ForbiddenError("Not a member of this workspace.", code="FORBIDDEN")

        members = await self.workspace_member_repo.list_members_with_user_details(workspace_id)
        return [
            WorkspaceMemberDetailResponse(
                user_id=user.id,
                email=user.email,
                full_name=user.full_name,
                role=member.role,
                joined_at=member.joined_at,
            )
            for member, user in members
        ]

    async def update_workspace(
        self, current_user: User, workspace_id: UUID, dto: WorkspaceUpdateRequest
    ) -> WorkspaceResponse:
        """Update workspace name."""
        workspace = await self.workspace_repo.get_by_id(workspace_id)
        if not workspace:
            raise NotFoundError("Workspace not found.", code="NOT_FOUND")

        if current_user.role != UserRole.ADMIN:
            caller_member = await self.workspace_member_repo.get_member(
                workspace_id, current_user.id
            )
            if not caller_member or caller_member.role != WorkspaceRole.OWNER:
                raise ForbiddenError(
                    "Only workspace OWNER or system ADMIN can update workspace.",
                    code="FORBIDDEN",
                )

        updated_workspace = await self.workspace_repo.update_workspace(workspace_id, dto.name)
        await self.db.commit()
        if updated_workspace:
            await self.db.refresh(updated_workspace)
            return WorkspaceResponse.model_validate(updated_workspace)
        raise NotFoundError("Workspace not found.", code="NOT_FOUND")

    async def delete_workspace(self, current_user: User, workspace_id: UUID) -> None:
        """Delete workspace and all associated entities (cascade)."""
        workspace = await self.workspace_repo.get_by_id(workspace_id)
        if not workspace:
            raise NotFoundError("Workspace not found.", code="NOT_FOUND")

        if current_user.role != UserRole.ADMIN:
            caller_member = await self.workspace_member_repo.get_member(
                workspace_id, current_user.id
            )
            if not caller_member or caller_member.role != WorkspaceRole.OWNER:
                raise ForbiddenError(
                    "Only workspace OWNER or system ADMIN can delete workspace.",
                    code="FORBIDDEN",
                )

        await self.workspace_repo.delete_by_id(workspace_id)
        await self.db.commit()
