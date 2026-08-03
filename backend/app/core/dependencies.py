from collections.abc import Callable
from typing import Any
from uuid import UUID

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.exceptions import UnauthorizedError
from app.core.redis import get_redis
from app.core.security import decode_token
from app.models.user import User
from app.repositories.user import UserRepository

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


def require_workspace_role(min_role: str) -> Callable[..., Any]:
    """Dependency factory for checking user workspace permissions.

    Full implementation will be added in Phase 6 (Workspace & RBAC).
    """

    async def dependency() -> Any:
        raise NotImplementedError("RBAC dependency factory scaffold")

    return dependency


def require_owner() -> Callable[..., Any]:
    """Shortcut dependency requiring OWNER role in workspace."""
    return require_workspace_role("OWNER")


def require_member() -> Callable[..., Any]:
    """Shortcut dependency requiring at least VIEWER role in workspace."""
    return require_workspace_role("VIEWER")
