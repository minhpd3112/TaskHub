from uuid import uuid4

import pytest
from httpx import AsyncClient

from app.core.redis import redis_client
from app.core.security import decode_token


@pytest.mark.asyncio
async def test_api_register_real_db(async_client: AsyncClient) -> None:
    """Real integration test: POST /api/v1/auth/register creates a user in PostgreSQL DB."""
    email = f"test_reg_{uuid4().hex[:8]}@taskhub.io"
    payload = {
        "email": email,
        "full_name": "Integration User",
        "password": "Password123!",
    }

    # 1. Register new user
    response = await async_client.post("/api/v1/auth/register", json=payload)
    assert response.status_code == 201
    data = response.json()["data"]
    assert data["email"] == email
    assert data["full_name"] == "Integration User"
    assert data["role"] == "MEMBER"
    assert data["is_active"] is True
    assert "hashed_password" not in data

    # 2. Attempt duplicate email registration -> 409 Conflict
    dup_response = await async_client.post("/api/v1/auth/register", json=payload)
    assert dup_response.status_code == 409
    dup_error = dup_response.json()["error"]
    assert dup_error["code"] == "EMAIL_ALREADY_EXISTS"


@pytest.mark.asyncio
async def test_api_login_real_db(async_client: AsyncClient) -> None:
    """Real integration test: POST /api/v1/auth/login authenticates against PostgreSQL DB."""
    email = f"test_login_{uuid4().hex[:8]}@taskhub.io"
    password = "Password123!"

    # Create account
    await async_client.post(
        "/api/v1/auth/register",
        json={"email": email, "full_name": "Login Test User", "password": password},
    )

    # 1. Login with correct password -> 200 OK
    response = await async_client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"
    assert data["user"]["email"] == email

    # 2. Login with wrong password -> 401 Unauthorized
    bad_login = await async_client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "WrongPassword!"},
    )
    assert bad_login.status_code == 401
    assert bad_login.json()["error"]["code"] == "INVALID_CREDENTIALS"


@pytest.mark.asyncio
async def test_api_refresh_token_real_db(async_client: AsyncClient) -> None:
    """Real integration test: POST /api/v1/auth/refresh issues a new access token."""
    email = f"test_refresh_{uuid4().hex[:8]}@taskhub.io"
    password = "Password123!"

    # Create account & login
    await async_client.post(
        "/api/v1/auth/register",
        json={"email": email, "full_name": "Refresh User", "password": password},
    )
    login_res = await async_client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    refresh_token = login_res.json()["data"]["refresh_token"]

    # Refresh access token
    response = await async_client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": refresh_token},
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert "access_token" in data
    assert data["token_type"] == "bearer"


@pytest.mark.asyncio
async def test_api_logout_and_real_redis_blacklist(async_client: AsyncClient) -> None:
    """Real integration test: POST /api/v1/auth/logout adds token JTIs to real Redis blacklist."""
    email = f"test_logout_{uuid4().hex[:8]}@taskhub.io"
    password = "Password123!"

    # 1. Register & Login
    await async_client.post(
        "/api/v1/auth/register",
        json={"email": email, "full_name": "Logout User", "password": password},
    )
    login_res = await async_client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    tokens = login_res.json()["data"]
    access_token = tokens["access_token"]
    refresh_token = tokens["refresh_token"]

    # Extract JTIs
    r_jti = decode_token(refresh_token)["jti"]
    a_jti = decode_token(access_token)["jti"]

    # 2. Call Logout API
    headers = {"Authorization": f"Bearer {access_token}"}
    logout_res = await async_client.post(
        "/api/v1/auth/logout",
        json={"refresh_token": refresh_token},
        headers=headers,
    )
    assert logout_res.status_code == 204

    # 3. Verify real Redis contains blacklisted JTIs
    r_blacklisted = await redis_client.get(f"token:blacklist:{r_jti}")
    a_blacklisted = await redis_client.get(f"token:blacklist:{a_jti}")
    assert r_blacklisted == "1"
    assert a_blacklisted == "1"

    # 4. Re-using revoked refresh token fails with 401 REFRESH_TOKEN_INVALID
    ref_res = await async_client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": refresh_token},
    )
    assert ref_res.status_code == 401
    assert ref_res.json()["error"]["code"] == "REFRESH_TOKEN_INVALID"
