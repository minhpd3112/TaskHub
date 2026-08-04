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


@pytest.mark.asyncio
async def test_list_workspaces_unauthenticated(async_client: AsyncClient) -> None:
    """Integration test: GET /api/v1/workspaces without Bearer token returns 401."""
    response = await async_client.get("/api/v1/workspaces")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHORIZED"


@pytest.mark.asyncio
async def test_list_workspaces_empty(async_client: AsyncClient) -> None:
    """Integration test: GET /api/v1/workspaces for user with no workspaces returns empty list."""
    email = f"ws_empty_{uuid4().hex[:8]}@taskhub.io"
    password = "Password123!"

    await async_client.post(
        "/api/v1/auth/register",
        json={"email": email, "full_name": "Empty User", "password": password},
    )
    login_res = await async_client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    access_token = login_res.json()["data"]["access_token"]
    headers = {"Authorization": f"Bearer {access_token}"}

    response = await async_client.get("/api/v1/workspaces", headers=headers)
    assert response.status_code == 200
    assert response.json()["data"] == []


@pytest.mark.asyncio
async def test_list_workspaces_success(async_client: AsyncClient) -> None:
    """Integration test: GET /api/v1/workspaces returns workspaces with role."""
    email = f"ws_list_{uuid4().hex[:8]}@taskhub.io"
    password = "Password123!"

    await async_client.post(
        "/api/v1/auth/register",
        json={"email": email, "full_name": "List User", "password": password},
    )
    login_res = await async_client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    access_token = login_res.json()["data"]["access_token"]
    headers = {"Authorization": f"Bearer {access_token}"}

    # Create 2 workspaces
    await async_client.post("/api/v1/workspaces", json={"name": "Workspace 1"}, headers=headers)
    await async_client.post("/api/v1/workspaces", json={"name": "Workspace 2"}, headers=headers)

    response = await async_client.get("/api/v1/workspaces", headers=headers)
    assert response.status_code == 200
    data = response.json()["data"]
    assert len(data) == 2
    names = {ws["name"] for ws in data}
    assert names == {"Workspace 1", "Workspace 2"}
    for ws in data:
        assert ws["role"] == "OWNER"
        assert "id" in ws
        assert "owner_id" in ws
        assert "created_at" in ws


@pytest.mark.asyncio
async def test_list_workspaces_data_isolation(async_client: AsyncClient) -> None:
    """Integration test: User A does not see User B's workspaces."""
    # Register User A
    email_a = f"user_a_{uuid4().hex[:8]}@taskhub.io"
    password_a = "Password123!"
    await async_client.post(
        "/api/v1/auth/register",
        json={"email": email_a, "full_name": "User A", "password": password_a},
    )
    login_a = await async_client.post(
        "/api/v1/auth/login",
        json={"email": email_a, "password": password_a},
    )
    headers_a = {"Authorization": f"Bearer {login_a.json()['data']['access_token']}"}

    # Register User B
    email_b = f"user_b_{uuid4().hex[:8]}@taskhub.io"
    password_b = "Password123!"
    await async_client.post(
        "/api/v1/auth/register",
        json={"email": email_b, "full_name": "User B", "password": password_b},
    )
    login_b = await async_client.post(
        "/api/v1/auth/login",
        json={"email": email_b, "password": password_b},
    )
    headers_b = {"Authorization": f"Bearer {login_b.json()['data']['access_token']}"}

    # User A creates WS A, User B creates WS B
    await async_client.post(
        "/api/v1/workspaces", json={"name": "Workspace of A"}, headers=headers_a
    )
    await async_client.post(
        "/api/v1/workspaces", json={"name": "Workspace of B"}, headers=headers_b
    )

    # Check User A's list
    res_a = await async_client.get("/api/v1/workspaces", headers=headers_a)
    assert res_a.status_code == 200
    data_a = res_a.json()["data"]
    assert len(data_a) == 1
    assert data_a[0]["name"] == "Workspace of A"

    # Check User B's list
    res_b = await async_client.get("/api/v1/workspaces", headers=headers_b)
    assert res_b.status_code == 200
    data_b = res_b.json()["data"]
    assert len(data_b) == 1
    assert data_b[0]["name"] == "Workspace of B"
