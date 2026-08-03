from uuid import uuid4

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_get_profile_api_success(async_client: AsyncClient) -> None:
    """Integration test: GET /api/v1/users/me returns authenticated user's profile."""
    email = f"user_me_{uuid4().hex[:8]}@taskhub.io"
    password = "Password123!"

    # 1. Register & Login
    await async_client.post(
        "/api/v1/auth/register",
        json={"email": email, "full_name": "Test User Me", "password": password},
    )
    login_res = await async_client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    access_token = login_res.json()["data"]["access_token"]
    headers = {"Authorization": f"Bearer {access_token}"}

    # 2. GET /api/v1/users/me
    response = await async_client.get("/api/v1/users/me", headers=headers)
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["email"] == email
    assert data["full_name"] == "Test User Me"
    assert data["role"] == "MEMBER"
    assert data["is_active"] is True
    assert "hashed_password" not in data


@pytest.mark.asyncio
async def test_get_profile_api_unauthorized(async_client: AsyncClient) -> None:
    """Integration test: GET /api/v1/users/me without token returns 401 Unauthorized."""
    response = await async_client.get("/api/v1/users/me")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHORIZED"


@pytest.mark.asyncio
async def test_update_profile_api_success(async_client: AsyncClient) -> None:
    """Integration test: PATCH /api/v1/users/me updates full_name."""
    email = f"user_update_{uuid4().hex[:8]}@taskhub.io"
    password = "Password123!"

    await async_client.post(
        "/api/v1/auth/register",
        json={"email": email, "full_name": "Old Name", "password": password},
    )
    login_res = await async_client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    access_token = login_res.json()["data"]["access_token"]
    headers = {"Authorization": f"Bearer {access_token}"}

    # PATCH /api/v1/users/me
    patch_res = await async_client.patch(
        "/api/v1/users/me",
        json={"full_name": "New Updated Name"},
        headers=headers,
    )
    assert patch_res.status_code == 200
    patch_data = patch_res.json()["data"]
    assert patch_data["full_name"] == "New Updated Name"

    # Verify via GET /api/v1/users/me
    get_res = await async_client.get("/api/v1/users/me", headers=headers)
    assert get_res.json()["data"]["full_name"] == "New Updated Name"


@pytest.mark.asyncio
async def test_update_profile_api_invalid_name(async_client: AsyncClient) -> None:
    """Integration test: PATCH /api/v1/users/me with empty name returns 422 Validation Error."""
    email = f"user_invalid_{uuid4().hex[:8]}@taskhub.io"
    password = "Password123!"

    await async_client.post(
        "/api/v1/auth/register",
        json={"email": email, "full_name": "Valid Name", "password": password},
    )
    login_res = await async_client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    access_token = login_res.json()["data"]["access_token"]
    headers = {"Authorization": f"Bearer {access_token}"}

    # Empty name
    response = await async_client.patch(
        "/api/v1/users/me",
        json={"full_name": "   "},
        headers=headers,
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_change_password_api_success(async_client: AsyncClient) -> None:
    """Integration test: POST /api/v1/users/me/password changes password successfully."""
    email = f"user_chpw_{uuid4().hex[:8]}@taskhub.io"
    old_password = "Password123!"
    new_password = "NewSecurePass456!"

    await async_client.post(
        "/api/v1/auth/register",
        json={"email": email, "full_name": "Pass User", "password": old_password},
    )
    login_res = await async_client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": old_password},
    )
    access_token = login_res.json()["data"]["access_token"]
    headers = {"Authorization": f"Bearer {access_token}"}

    # 1. Change password
    chpw_res = await async_client.post(
        "/api/v1/users/me/password",
        json={"current_password": old_password, "new_password": new_password},
        headers=headers,
    )
    assert chpw_res.status_code == 204

    # 2. Attempt login with old password -> 401
    old_login_res = await async_client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": old_password},
    )
    assert old_login_res.status_code == 401

    # 3. Login with new password -> 200 OK
    new_login_res = await async_client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": new_password},
    )
    assert new_login_res.status_code == 200


@pytest.mark.asyncio
async def test_change_password_api_wrong_current_password(async_client: AsyncClient) -> None:
    """Integration test: POST /api/v1/users/me/password with wrong current password returns 401."""
    email = f"user_wrongpw_{uuid4().hex[:8]}@taskhub.io"
    password = "Password123!"

    await async_client.post(
        "/api/v1/auth/register",
        json={"email": email, "full_name": "Pass User", "password": password},
    )
    login_res = await async_client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    access_token = login_res.json()["data"]["access_token"]
    headers = {"Authorization": f"Bearer {access_token}"}

    # Wrong current password
    chpw_res = await async_client.post(
        "/api/v1/users/me/password",
        json={"current_password": "WrongPassword1!", "new_password": "NewSecurePass456!"},
        headers=headers,
    )
    assert chpw_res.status_code == 401
    assert chpw_res.json()["error"]["code"] == "WRONG_PASSWORD"
