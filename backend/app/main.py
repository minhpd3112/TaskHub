import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.api.health import router as health_router
from app.api.v1.router import router as v1_router
from app.core.config import settings
from app.core.exceptions import (
    ConflictError,
    ForbiddenError,
    NotFoundError,
    TaskHubError,
    TokenExpiredError,
    TokenInvalidError,
    UnauthorizedError,
    ValidationError,
)
from app.core.logging import setup_logging
from app.core.middleware import setup_middleware
from app.schemas.common import ErrorBody, ErrorResponse

logger = logging.getLogger("app.main")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan context manager for startup and shutdown events."""
    setup_logging()
    logger.info(f"Starting {settings.APP_NAME} v{settings.APP_VERSION}")
    yield
    logger.info(f"Shutting down {settings.APP_NAME}")


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Task Management System — Backend API",
    openapi_tags=[
        {
            "name": "Health",
            "description": "Health check and system status operations.",
        },
        {
            "name": "Auth",
            "description": "Authentication operations (register, login, refresh, logout).",
        },
        {
            "name": "Users",
            "description": "User profile management operations.",
        },
        {
            "name": "Workspaces",
            "description": "Workspace management and membership operations.",
        },
        {
            "name": "Projects",
            "description": "Project management operations.",
        },
        {
            "name": "Tasks",
            "description": "Task management operations.",
        },
        {
            "name": "Labels",
            "description": "Label management operations.",
        },
        {
            "name": "Comments",
            "description": "Task comment operations.",
        },
    ],
    lifespan=lifespan,
)

# Setup CORS and custom middlewares
setup_middleware(app)


# Global Exception Handlers
@app.exception_handler(TaskHubError)
async def taskhub_exception_handler(request: Request, exc: TaskHubError) -> JSONResponse:
    status_code = 500
    if isinstance(exc, NotFoundError):
        status_code = 404
    elif isinstance(exc, ForbiddenError):
        status_code = 403
    elif isinstance(exc, ConflictError):
        status_code = 409
    elif isinstance(exc, ValidationError):
        status_code = 400
    elif isinstance(exc, UnauthorizedError | TokenExpiredError | TokenInvalidError):
        status_code = 401

    error_response = ErrorResponse(
        error=ErrorBody(
            code=exc.code,
            message=exc.message,
            details=exc.details,
        )
    )
    return JSONResponse(status_code=status_code, content=error_response.model_dump())


# Routers registration
app.include_router(health_router)
app.include_router(v1_router, prefix="/api/v1")
