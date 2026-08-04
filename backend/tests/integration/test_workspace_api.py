from uuid import uuid4

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_create_workspace_success(async_client: AsyncClient) -> None:
    """Integration test: POST /api/v1/workspaces creates workspace and assigns OWNER."""
    email = f"ws_owner_{uuid4().hex[:8]}@taskhub.io"
    password = "Password123!"

    # 1. Register & Login
    await async_client.post(
        "/api/v1/auth/register",
        json={"email": email, "full_name": "Workspace Owner", "password": password},
    )
    login_res = await async_client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    access_token = login_res.json()["data"]["access_token"]
    headers = {"Authorization": f"Bearer {access_token}"}

    # 2. POST /api/v1/workspaces
    response = await async_client.post(
        "/api/v1/workspaces",
        json={"name": "Backend Engineering"},
        headers=headers,
    )
    assert response.status_code == 201
    data = response.json()["data"]
    assert data["name"] == "Backend Engineering"
    assert "id" in data
    assert "owner_id" in data
    assert "created_at" in data


@pytest.mark.asyncio
async def test_create_workspace_missing_or_empty_name(async_client: AsyncClient) -> None:
    """Integration test: POST /api/v1/workspaces with empty or missing name returns 422."""
    email = f"ws_invalid_{uuid4().hex[:8]}@taskhub.io"
    password = "Password123!"

    await async_client.post(
        "/api/v1/auth/register",
        json={"email": email, "full_name": "Test User", "password": password},
    )
    login_res = await async_client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    access_token = login_res.json()["data"]["access_token"]
    headers = {"Authorization": f"Bearer {access_token}"}

    # Missing name field
    res1 = await async_client.post(
        "/api/v1/workspaces",
        json={},
        headers=headers,
    )
    assert res1.status_code == 422

    # Empty string name
    res2 = await async_client.post(
        "/api/v1/workspaces",
        json={"name": ""},
        headers=headers,
    )
    assert res2.status_code == 422

    # Whitespace only name
    res3 = await async_client.post(
        "/api/v1/workspaces",
        json={"name": "   "},
        headers=headers,
    )
    assert res3.status_code == 422


@pytest.mark.asyncio
async def test_create_workspace_name_too_long(async_client: AsyncClient) -> None:
    """Integration test: POST /api/v1/workspaces with name > 100 chars returns 422."""
    email = f"ws_long_{uuid4().hex[:8]}@taskhub.io"
    password = "Password123!"

    await async_client.post(
        "/api/v1/auth/register",
        json={"email": email, "full_name": "Test User", "password": password},
    )
    login_res = await async_client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    access_token = login_res.json()["data"]["access_token"]
    headers = {"Authorization": f"Bearer {access_token}"}

    # Name with 101 characters
    res = await async_client.post(
        "/api/v1/workspaces",
        json={"name": "a" * 101},
        headers=headers,
    )
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_create_workspace_unauthenticated(async_client: AsyncClient) -> None:
    """Integration test: POST /api/v1/workspaces without Bearer token returns 401."""
    response = await async_client.post(
        "/api/v1/workspaces",
        json={"name": "Unauthorized Workspace"},
    )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHORIZED"
