from collections.abc import Callable
from typing import Any
from uuid import UUID

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.exceptions import ForbiddenError, NotFoundError, UnauthorizedError
from app.core.redis import get_redis
from app.core.security import decode_token
from app.models.enums import UserRole, WorkspaceRole
from app.models.user import User
from app.models.workspace import WorkspaceMember
from app.repositories.user import UserRepository
from app.repositories.workspace import WorkspaceRepository

http_bearer = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(http_bearer),
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
) -> User:
    """Dependency to retrieve and validate current authenticated user from Bearer JWT token."""
    if not credentials or not credentials.credentials:
        raise UnauthorizedError("Authentication token required.", code="UNAUTHORIZED")

    token = credentials.credentials
    payload = decode_token(token)

    if payload.get("type") != "access":
        raise UnauthorizedError("Invalid token type. Access token required.", code="UNAUTHORIZED")

    jti = payload.get("jti")
    if jti:
        is_blacklisted = await redis.get(f"token:blacklist:{jti}")
        if is_blacklisted:
            raise UnauthorizedError("Token has been revoked.", code="UNAUTHORIZED")

    sub = payload.get("sub")
    if not sub:
        raise UnauthorizedError("Invalid token payload.", code="UNAUTHORIZED")

    try:
        user_id = UUID(sub)
    except ValueError as e:
        raise UnauthorizedError("Invalid user ID in token.", code="UNAUTHORIZED") from e

    user_repo = UserRepository(db)
    user = await user_repo.get_by_id(user_id)
    if not user:
        raise UnauthorizedError("User does not exist.", code="UNAUTHORIZED")

    if not user.is_active:
        raise UnauthorizedError("User account is inactive.", code="ACCOUNT_INACTIVE")

    return user


def require_workspace_role(min_role: WorkspaceRole | str) -> Callable[..., Any]:
    """Dependency factory for checking user workspace permissions.

    Roles rank: OWNER (3) > EDITOR (2) > VIEWER (1).
    ADMIN role bypasses workspace role checks.
    """
    target_role = WorkspaceRole(min_role) if isinstance(min_role, str) else min_role

    async def dependency(
        workspace_id: UUID,
        current_user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db),
    ) -> WorkspaceMember:
        workspace_repo = WorkspaceRepository(db)

        # 1. Admin bypass check
        if current_user.role == UserRole.ADMIN:
            workspace = await workspace_repo.get_by_id(workspace_id)
            if not workspace:
                raise NotFoundError("Workspace không tồn tại.", code="NOT_FOUND")
            return WorkspaceMember(
                workspace_id=workspace_id,
                user_id=current_user.id,
                role=WorkspaceRole.OWNER,
            )

        # 2. Check workspace existence
        workspace = await workspace_repo.get_by_id(workspace_id)
        if not workspace:
            raise NotFoundError("Workspace không tồn tại.", code="NOT_FOUND")

        # 3. Check workspace membership
        member = await workspace_repo.get_member(workspace_id, current_user.id)
        if not member:
            raise NotFoundError(
                "Workspace không tồn tại.",
                code="NOT_FOUND",
            )

        # 4. Check role hierarchy
        role_hierarchy = {
            WorkspaceRole.OWNER: 3,
            WorkspaceRole.EDITOR: 2,
            WorkspaceRole.VIEWER: 1,
        }

        user_rank = role_hierarchy.get(member.role, 0)
        req_rank = role_hierarchy.get(target_role, 1)

        if user_rank < req_rank:
            raise ForbiddenError(
                f"Yêu cầu quyền tối thiểu là {target_role.value}.",
                code="FORBIDDEN",
            )

        return member

    return dependency


def require_owner() -> Callable[..., Any]:
    """Shortcut dependency requiring OWNER role in workspace."""
    return require_workspace_role(WorkspaceRole.OWNER)


def require_member() -> Callable[..., Any]:
    """Shortcut dependency requiring at least VIEWER role in workspace."""
    return require_workspace_role(WorkspaceRole.VIEWER)
