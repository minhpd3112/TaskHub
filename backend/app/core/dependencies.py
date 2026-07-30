from collections.abc import Callable
from typing import Any


async def get_current_user() -> Any:
    """Dependency placeholder for getting the current authenticated user.

    Full implementation will be added in Phase 5 (Auth Feature).
    """
    raise NotImplementedError("UserRepository is required for get_current_user")


def require_workspace_role(min_role: str) -> Callable[..., Any]:
    """Dependency factory for checking user workspace permissions.

    Full implementation will be added in Phase 5 (Auth & RBAC).
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
