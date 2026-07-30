import logging
import time
from collections.abc import Awaitable, Callable

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings

logger = logging.getLogger("app.middleware")


def setup_middleware(app: FastAPI) -> None:
    """Configure CORS and custom middlewares for FastAPI app."""
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.ALLOWED_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def log_requests(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        start_time = time.perf_counter()
        response = await call_next(request)
        process_time = (time.perf_counter() - start_time) * 1000
        logger.info(
            "%s %s - Status: %d - Duration: %.2fms",
            request.method,
            request.url.path,
            response.status_code,
            process_time,
        )
        return response
