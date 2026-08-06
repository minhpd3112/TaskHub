from uuid import uuid4

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_get_settings_default_values(async_client: AsyncClient) -> None:
    """Test GET /api/v1/notifications/settings returns default settings."""
    email = f"notif_def_{uuid4().hex[:8]}@taskhub.io"
    password = "Password123!"

    await async_client.post(
        "/api/v1/auth/register",
        json={"email": email, "full_name": "Notif User Def", "password": password},
    )
    login_res = await async_client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    token = login_res.json()["data"]["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    res = await async_client.get("/api/v1/notifications/settings", headers=headers)
    assert res.status_code == 200
    data = res.json()["data"]
    assert data["task_assigned"] is True
    assert data["task_status_changed"] is True
    assert data["task_commented"] is True


@pytest.mark.asyncio
async def test_get_settings_unauthorized(async_client: AsyncClient) -> None:
    """Test GET /api/v1/notifications/settings without token returns 401."""
    res = await async_client.get("/api/v1/notifications/settings")
    assert res.status_code == 401
    assert res.json()["error"]["code"] == "UNAUTHORIZED"


@pytest.mark.asyncio
async def test_update_settings_success(async_client: AsyncClient) -> None:
    """Test PATCH /api/v1/notifications/settings updates optional fields."""
    email = f"notif_upd_{uuid4().hex[:8]}@taskhub.io"
    password = "Password123!"

    await async_client.post(
        "/api/v1/auth/register",
        json={"email": email, "full_name": "Notif User Upd", "password": password},
    )
    login_res = await async_client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    token = login_res.json()["data"]["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 1. Update status_changed and commented to False
    patch_res = await async_client.patch(
        "/api/v1/notifications/settings",
        json={"task_status_changed": False, "task_commented": False},
        headers=headers,
    )
    assert patch_res.status_code == 200
    patch_data = patch_res.json()["data"]
    assert patch_data["task_assigned"] is True
    assert patch_data["task_status_changed"] is False
    assert patch_data["task_commented"] is False

    # 2. Verify via GET endpoint
    get_res = await async_client.get("/api/v1/notifications/settings", headers=headers)
    assert get_res.status_code == 200
    get_data = get_res.json()["data"]
    assert get_data["task_status_changed"] is False
    assert get_data["task_commented"] is False


@pytest.mark.asyncio
async def test_update_settings_task_assigned_false_returns_400(
    async_client: AsyncClient,
) -> None:
    """Test PATCH /api/v1/notifications/settings with task_assigned: false returns 400/422."""
    email = f"notif_err_{uuid4().hex[:8]}@taskhub.io"
    password = "Password123!"

    await async_client.post(
        "/api/v1/auth/register",
        json={"email": email, "full_name": "Notif User Err", "password": password},
    )
    login_res = await async_client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    token = login_res.json()["data"]["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    patch_res = await async_client.patch(
        "/api/v1/notifications/settings",
        json={"task_assigned": False},
        headers=headers,
    )
    assert patch_res.status_code in (400, 422)


@pytest.mark.asyncio
async def test_idor_isolation(async_client: AsyncClient) -> None:
    """Integration test: User A settings updates do not affect User B settings (IDOR protection)."""
    # Create User A
    email_a = f"notif_user_a_{uuid4().hex[:8]}@taskhub.io"
    password = "Password123!"
    await async_client.post(
        "/api/v1/auth/register",
        json={"email": email_a, "full_name": "User A", "password": password},
    )
    login_a = await async_client.post(
        "/api/v1/auth/login", json={"email": email_a, "password": password}
    )
    token_a = login_a.json()["data"]["access_token"]

    # Create User B
    email_b = f"notif_user_b_{uuid4().hex[:8]}@taskhub.io"
    await async_client.post(
        "/api/v1/auth/register",
        json={"email": email_b, "full_name": "User B", "password": password},
    )
    login_b = await async_client.post(
        "/api/v1/auth/login", json={"email": email_b, "password": password}
    )
    token_b = login_b.json()["data"]["access_token"]

    # User A disables task_status_changed
    await async_client.patch(
        "/api/v1/notifications/settings",
        json={"task_status_changed": False},
        headers={"Authorization": f"Bearer {token_a}"},
    )

    # User B checks settings -> task_status_changed remains True
    res_b = await async_client.get(
        "/api/v1/notifications/settings",
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert res_b.status_code == 200
    assert res_b.json()["data"]["task_status_changed"] is True
