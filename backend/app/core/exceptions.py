from typing import Any


class TaskHubError(Exception):
    """Base exception class for TaskHub application."""

    def __init__(
        self,
        message: str = "An unexpected error occurred.",
        code: str = "INTERNAL_ERROR",
        details: Any = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.code = code
        self.details = details


class NotFoundError(TaskHubError):
    """Raised when a requested resource is not found (HTTP 404)."""

    def __init__(
        self,
        message: str = "Resource not found.",
        code: str = "NOT_FOUND",
        details: Any = None,
    ) -> None:
        super().__init__(message=message, code=code, details=details)


class ForbiddenError(TaskHubError):
    """Raised when access to a resource is forbidden (HTTP 403)."""

    def __init__(
        self,
        message: str = "Permission denied.",
        code: str = "FORBIDDEN",
        details: Any = None,
    ) -> None:
        super().__init__(message=message, code=code, details=details)


class ConflictError(TaskHubError):
    """Raised when a resource conflict occurs (HTTP 409)."""

    def __init__(
        self,
        message: str = "Resource conflict.",
        code: str = "CONFLICT",
        details: Any = None,
    ) -> None:
        super().__init__(message=message, code=code, details=details)


class ValidationError(TaskHubError):
    """Raised when input validation fails (HTTP 400)."""

    def __init__(
        self,
        message: str = "Validation failed.",
        code: str = "VALIDATION_ERROR",
        details: Any = None,
    ) -> None:
        super().__init__(message=message, code=code, details=details)


class UnauthorizedError(TaskHubError):
    """Raised when authentication fails or credentials are missing (HTTP 401)."""

    def __init__(
        self,
        message: str = "Authentication required.",
        code: str = "UNAUTHORIZED",
        details: Any = None,
    ) -> None:
        super().__init__(message=message, code=code, details=details)


class TokenExpiredError(UnauthorizedError):
    """Raised when a JWT token has expired (HTTP 401)."""

    def __init__(self, message: str = "Token has expired.", details: Any = None) -> None:
        super().__init__(message=message, code="TOKEN_EXPIRED", details=details)


class TokenInvalidError(UnauthorizedError):
    """Raised when a JWT token is invalid or malformed (HTTP 401)."""

    def __init__(self, message: str = "Invalid token.", details: Any = None) -> None:
        super().__init__(message=message, code="TOKEN_INVALID", details=details)
