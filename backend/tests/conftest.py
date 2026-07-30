"""Pytest root configuration and shared fixtures scaffold."""

from collections.abc import AsyncGenerator

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.fixture
async def async_client() -> AsyncGenerator[AsyncClient, None]:
    """Fixture providing an HTTPX AsyncClient bound to the FastAPI application."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        yield client
