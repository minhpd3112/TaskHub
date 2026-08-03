"""Pytest root configuration and shared fixtures scaffold."""

from collections.abc import AsyncGenerator

import pytest
from httpx import AsyncClient


@pytest.fixture
async def async_client() -> AsyncGenerator[AsyncClient, None]:
    """Fixture providing an HTTPX AsyncClient targeting the live running TaskHub API server."""
    async with AsyncClient(base_url="http://localhost:8000") as client:
        yield client
