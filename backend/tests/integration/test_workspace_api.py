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


@pytest.mark.asyncio
async def test_workspace_member_full_lifecycle(async_client: AsyncClient) -> None:
    """Integration test: Full lifecycle of member invite, list, update role, and remove."""
    # 1. Register Owner
    owner_email = f"ws_owner_{uuid4().hex[:8]}@taskhub.io"
    password = "Password123!"
    await async_client.post(
        "/api/v1/auth/register",
        json={"email": owner_email, "full_name": "Workspace Owner", "password": password},
    )
    login_owner = await async_client.post(
        "/api/v1/auth/login",
        json={"email": owner_email, "password": password},
    )
    owner_headers = {"Authorization": f"Bearer {login_owner.json()['data']['access_token']}"}

    # 2. Register Invitee
    invitee_email = f"ws_member_{uuid4().hex[:8]}@taskhub.io"
    reg_invitee = await async_client.post(
        "/api/v1/auth/register",
        json={"email": invitee_email, "full_name": "Invitee Member", "password": password},
    )
    invitee_user_id = reg_invitee.json()["data"]["id"]

    # 3. Create Workspace
    ws_res = await async_client.post(
        "/api/v1/workspaces",
        json={"name": "Lifecycle Workspace"},
        headers=owner_headers,
    )
    ws_id = ws_res.json()["data"]["id"]

    # 4. Invite Invitee as EDITOR
    invite_res = await async_client.post(
        f"/api/v1/workspaces/{ws_id}/members",
        json={"email": invitee_email, "role": "EDITOR"},
        headers=owner_headers,
    )
    assert invite_res.status_code == 201
    assert invite_res.json()["data"]["user_id"] == invitee_user_id
    assert invite_res.json()["data"]["role"] == "EDITOR"

    # 5. List members
    list_res = await async_client.get(
        f"/api/v1/workspaces/{ws_id}/members",
        headers=owner_headers,
    )
    assert list_res.status_code == 200
    members = list_res.json()["data"]
    assert len(members) == 2
    roles = {m["user_id"]: m["role"] for m in members}
    assert roles[invitee_user_id] == "EDITOR"

    # 6. Update role to VIEWER
    update_res = await async_client.patch(
        f"/api/v1/workspaces/{ws_id}/members/{invitee_user_id}",
        json={"role": "VIEWER"},
        headers=owner_headers,
    )
    assert update_res.status_code == 200
    assert update_res.json()["data"]["role"] == "VIEWER"

    # 7. Remove member
    remove_res = await async_client.delete(
        f"/api/v1/workspaces/{ws_id}/members/{invitee_user_id}",
        headers=owner_headers,
    )
    assert remove_res.status_code == 204

    # 8. List members again
    list_res2 = await async_client.get(
        f"/api/v1/workspaces/{ws_id}/members",
        headers=owner_headers,
    )
    assert list_res2.status_code == 200
    assert len(list_res2.json()["data"]) == 1


@pytest.mark.asyncio
async def test_invite_member_errors(async_client: AsyncClient) -> None:
    """Integration test: Invite non-existent email (404) and invite already member (409)."""
    owner_email = f"ws_err_owner_{uuid4().hex[:8]}@taskhub.io"
    password = "Password123!"
    await async_client.post(
        "/api/v1/auth/register",
        json={"email": owner_email, "full_name": "Error Owner", "password": password},
    )
    login_owner = await async_client.post(
        "/api/v1/auth/login",
        json={"email": owner_email, "password": password},
    )
    owner_headers = {"Authorization": f"Bearer {login_owner.json()['data']['access_token']}"}

    ws_res = await async_client.post(
        "/api/v1/workspaces",
        json={"name": "Error Workspace"},
        headers=owner_headers,
    )
    ws_id = ws_res.json()["data"]["id"]

    # 1. Invite non-existent email -> 404
    res1 = await async_client.post(
        f"/api/v1/workspaces/{ws_id}/members",
        json={"email": "nobody_exists_123456@taskhub.io"},
        headers=owner_headers,
    )
    assert res1.status_code == 404
    assert res1.json()["error"]["code"] == "USER_NOT_FOUND"

    # 2. Invite self (owner is already member) -> 409
    res2 = await async_client.post(
        f"/api/v1/workspaces/{ws_id}/members",
        json={"email": owner_email},
        headers=owner_headers,
    )
    assert res2.status_code == 409
    assert res2.json()["error"]["code"] == "ALREADY_MEMBER"


@pytest.mark.asyncio
async def test_member_permission_denied(async_client: AsyncClient) -> None:
    """Integration test: EDITOR/VIEWER cannot invite, update, or remove members (403)."""
    owner_email = f"ws_perm_owner_{uuid4().hex[:8]}@taskhub.io"
    member_email = f"ws_perm_editor_{uuid4().hex[:8]}@taskhub.io"
    password = "Password123!"

    # Register Owner
    await async_client.post(
        "/api/v1/auth/register",
        json={"email": owner_email, "full_name": "Owner", "password": password},
    )
    login_owner = await async_client.post(
        "/api/v1/auth/login", json={"email": owner_email, "password": password}
    )
    owner_headers = {"Authorization": f"Bearer {login_owner.json()['data']['access_token']}"}

    # Register Editor
    reg_editor = await async_client.post(
        "/api/v1/auth/register",
        json={"email": member_email, "full_name": "Editor", "password": password},
    )
    editor_id = reg_editor.json()["data"]["id"]
    login_editor = await async_client.post(
        "/api/v1/auth/login", json={"email": member_email, "password": password}
    )
    editor_headers = {"Authorization": f"Bearer {login_editor.json()['data']['access_token']}"}

    # Create WS & invite Editor
    ws_res = await async_client.post(
        "/api/v1/workspaces", json={"name": "Perm Workspace"}, headers=owner_headers
    )
    ws_id = ws_res.json()["data"]["id"]
    await async_client.post(
        f"/api/v1/workspaces/{ws_id}/members",
        json={"email": member_email, "role": "EDITOR"},
        headers=owner_headers,
    )

    # Editor tries to invite -> 403
    res_invite = await async_client.post(
        f"/api/v1/workspaces/{ws_id}/members",
        json={"email": "someone@taskhub.io"},
        headers=editor_headers,
    )
    assert res_invite.status_code == 403
    assert res_invite.json()["error"]["code"] == "FORBIDDEN"

    # Editor tries to update role -> 403
    res_update = await async_client.patch(
        f"/api/v1/workspaces/{ws_id}/members/{editor_id}",
        json={"role": "OWNER"},
        headers=editor_headers,
    )
    assert res_update.status_code == 403
    assert res_update.json()["error"]["code"] == "FORBIDDEN"

    # Editor tries to remove member -> 403
    res_delete = await async_client.delete(
        f"/api/v1/workspaces/{ws_id}/members/{editor_id}",
        headers=editor_headers,
    )
    assert res_delete.status_code == 403
    assert res_delete.json()["error"]["code"] == "FORBIDDEN"


@pytest.mark.asyncio
async def test_last_owner_protection(async_client: AsyncClient) -> None:
    """Integration test: Demoting or removing the last OWNER returns 400."""
    owner_email = f"ws_last_owner_{uuid4().hex[:8]}@taskhub.io"
    password = "Password123!"

    reg_res = await async_client.post(
        "/api/v1/auth/register",
        json={"email": owner_email, "full_name": "Last Owner", "password": password},
    )
    owner_id = reg_res.json()["data"]["id"]

    login_res = await async_client.post(
        "/api/v1/auth/login", json={"email": owner_email, "password": password}
    )
    owner_headers = {"Authorization": f"Bearer {login_res.json()['data']['access_token']}"}

    ws_res = await async_client.post(
        "/api/v1/workspaces", json={"name": "Last Owner Workspace"}, headers=owner_headers
    )
    ws_id = ws_res.json()["data"]["id"]

    # Demote last owner -> 400
    demote_res = await async_client.patch(
        f"/api/v1/workspaces/{ws_id}/members/{owner_id}",
        json={"role": "EDITOR"},
        headers=owner_headers,
    )
    assert demote_res.status_code == 400
    assert demote_res.json()["error"]["code"] == "CANNOT_DEMOTE_LAST_OWNER"

    # Remove last owner -> 400
    remove_res = await async_client.delete(
        f"/api/v1/workspaces/{ws_id}/members/{owner_id}",
        headers=owner_headers,
    )
    assert remove_res.status_code == 400
    assert remove_res.json()["error"]["code"] == "CANNOT_REMOVE_OWNER"


@pytest.mark.asyncio
async def test_update_workspace_api_success(async_client: AsyncClient) -> None:
    """Integration test: PATCH /api/v1/workspaces/{id} updates workspace name (200 OK)."""
    owner_email = f"ws_update_{uuid4().hex[:8]}@taskhub.io"
    password = "Password123!"

    await async_client.post(
        "/api/v1/auth/register",
        json={"email": owner_email, "full_name": "Update Owner", "password": password},
    )
    login_res = await async_client.post(
        "/api/v1/auth/login", json={"email": owner_email, "password": password}
    )
    owner_headers = {"Authorization": f"Bearer {login_res.json()['data']['access_token']}"}

    ws_res = await async_client.post(
        "/api/v1/workspaces", json={"name": "Initial Name"}, headers=owner_headers
    )
    ws_id = ws_res.json()["data"]["id"]

    # PATCH /api/v1/workspaces/{ws_id}
    patch_res = await async_client.patch(
        f"/api/v1/workspaces/{ws_id}",
        json={"name": "Renamed Workspace"},
        headers=owner_headers,
    )
    assert patch_res.status_code == 200
    assert patch_res.json()["data"]["name"] == "Renamed Workspace"
    assert patch_res.json()["data"]["id"] == ws_id


@pytest.mark.asyncio
async def test_update_workspace_api_validation(async_client: AsyncClient) -> None:
    """Integration test: PATCH /api/v1/workspaces/{id} with empty name returns 422."""
    owner_email = f"ws_val_{uuid4().hex[:8]}@taskhub.io"
    password = "Password123!"

    await async_client.post(
        "/api/v1/auth/register",
        json={"email": owner_email, "full_name": "Val Owner", "password": password},
    )
    login_res = await async_client.post(
        "/api/v1/auth/login", json={"email": owner_email, "password": password}
    )
    owner_headers = {"Authorization": f"Bearer {login_res.json()['data']['access_token']}"}

    ws_res = await async_client.post(
        "/api/v1/workspaces", json={"name": "Valid Name"}, headers=owner_headers
    )
    ws_id = ws_res.json()["data"]["id"]

    # Empty string name -> 422
    res_empty = await async_client.patch(
        f"/api/v1/workspaces/{ws_id}",
        json={"name": ""},
        headers=owner_headers,
    )
    assert res_empty.status_code == 422

    # Whitespace name -> 422
    res_spaces = await async_client.patch(
        f"/api/v1/workspaces/{ws_id}",
        json={"name": "   "},
        headers=owner_headers,
    )
    assert res_spaces.status_code == 422


@pytest.mark.asyncio
async def test_update_and_delete_workspace_not_found(async_client: AsyncClient) -> None:
    """Integration test: PATCH/DELETE non-existent workspace returns 404."""
    email = f"ws_nf_{uuid4().hex[:8]}@taskhub.io"
    password = "Password123!"

    await async_client.post(
        "/api/v1/auth/register",
        json={"email": email, "full_name": "NF User", "password": password},
    )
    login_res = await async_client.post(
        "/api/v1/auth/login", json={"email": email, "password": password}
    )
    headers = {"Authorization": f"Bearer {login_res.json()['data']['access_token']}"}

    fake_id = str(uuid4())
    res_patch = await async_client.patch(
        f"/api/v1/workspaces/{fake_id}",
        json={"name": "New Name"},
        headers=headers,
    )
    assert res_patch.status_code == 404
    assert res_patch.json()["error"]["code"] == "NOT_FOUND"

    res_delete = await async_client.delete(
        f"/api/v1/workspaces/{fake_id}",
        headers=headers,
    )
    assert res_delete.status_code == 404
    assert res_delete.json()["error"]["code"] == "NOT_FOUND"


@pytest.mark.asyncio
async def test_update_and_delete_workspace_forbidden(async_client: AsyncClient) -> None:
    """Integration test: EDITOR role cannot update or delete workspace (403 FORBIDDEN)."""
    owner_email = f"ws_fb_owner_{uuid4().hex[:8]}@taskhub.io"
    editor_email = f"ws_fb_editor_{uuid4().hex[:8]}@taskhub.io"
    password = "Password123!"

    # Register Owner
    await async_client.post(
        "/api/v1/auth/register",
        json={"email": owner_email, "full_name": "Owner", "password": password},
    )
    login_owner = await async_client.post(
        "/api/v1/auth/login", json={"email": owner_email, "password": password}
    )
    owner_headers = {"Authorization": f"Bearer {login_owner.json()['data']['access_token']}"}

    # Register Editor
    await async_client.post(
        "/api/v1/auth/register",
        json={"email": editor_email, "full_name": "Editor", "password": password},
    )
    login_editor = await async_client.post(
        "/api/v1/auth/login", json={"email": editor_email, "password": password}
    )
    editor_headers = {"Authorization": f"Bearer {login_editor.json()['data']['access_token']}"}

    # Create WS & invite Editor
    ws_res = await async_client.post(
        "/api/v1/workspaces", json={"name": "Shared WS"}, headers=owner_headers
    )
    ws_id = ws_res.json()["data"]["id"]
    await async_client.post(
        f"/api/v1/workspaces/{ws_id}/members",
        json={"email": editor_email, "role": "EDITOR"},
        headers=owner_headers,
    )

    # Editor tries to update name -> 403
    patch_res = await async_client.patch(
        f"/api/v1/workspaces/{ws_id}",
        json={"name": "Hacked Name"},
        headers=editor_headers,
    )
    assert patch_res.status_code == 403
    assert patch_res.json()["error"]["code"] == "FORBIDDEN"

    # Editor tries to delete workspace -> 403
    del_res = await async_client.delete(
        f"/api/v1/workspaces/{ws_id}",
        headers=editor_headers,
    )
    assert del_res.status_code == 403
    assert del_res.json()["error"]["code"] == "FORBIDDEN"


@pytest.mark.asyncio
async def test_delete_workspace_api_success_and_cascade(async_client: AsyncClient) -> None:
    """Integration test: DELETE /api/v1/workspaces/{id} deletes workspace (204 No Content).

    Also verifies users remain intact.
    """
    owner_email = f"del_owner_{uuid4().hex[:8]}@taskhub.io"
    member_email = f"del_member_{uuid4().hex[:8]}@taskhub.io"
    password = "Password123!"

    # 1. Register Owner & Member
    await async_client.post(
        "/api/v1/auth/register",
        json={"email": owner_email, "full_name": "Owner User", "password": password},
    )
    await async_client.post(
        "/api/v1/auth/register",
        json={"email": member_email, "full_name": "Member User", "password": password},
    )

    login_owner = await async_client.post(
        "/api/v1/auth/login", json={"email": owner_email, "password": password}
    )
    owner_headers = {"Authorization": f"Bearer {login_owner.json()['data']['access_token']}"}

    # 2. Create Workspace
    ws_res = await async_client.post(
        "/api/v1/workspaces", json={"name": "Workspace to Delete"}, headers=owner_headers
    )
    ws_id = ws_res.json()["data"]["id"]

    # 3. Add Member
    await async_client.post(
        f"/api/v1/workspaces/{ws_id}/members",
        json={"email": member_email, "role": "EDITOR"},
        headers=owner_headers,
    )

    # 4. Delete Workspace
    delete_res = await async_client.delete(
        f"/api/v1/workspaces/{ws_id}",
        headers=owner_headers,
    )
    assert delete_res.status_code == 204

    # 5. Verify Workspace is gone
    list_res = await async_client.get("/api/v1/workspaces", headers=owner_headers)
    assert list_res.status_code == 200
    assert not any(w["id"] == ws_id for w in list_res.json()["data"])

    # 6. Verify User accounts remain intact (Owner & Member can still log in and view profile)
    login_owner_again = await async_client.post(
        "/api/v1/auth/login", json={"email": owner_email, "password": password}
    )
    assert login_owner_again.status_code == 200

    login_member_again = await async_client.post(
        "/api/v1/auth/login", json={"email": member_email, "password": password}
    )
    assert login_member_again.status_code == 200


@pytest.mark.asyncio
async def test_update_workspace_api_name_too_long(async_client: AsyncClient) -> None:
    """Integration test: PATCH /api/v1/workspaces/{id} with name > 100 chars returns 422."""
    owner_email = f"ws_long_patch_{uuid4().hex[:8]}@taskhub.io"
    password = "Password123!"

    await async_client.post(
        "/api/v1/auth/register",
        json={"email": owner_email, "full_name": "Long Name User", "password": password},
    )
    login_res = await async_client.post(
        "/api/v1/auth/login", json={"email": owner_email, "password": password}
    )
    owner_headers = {"Authorization": f"Bearer {login_res.json()['data']['access_token']}"}

    ws_res = await async_client.post(
        "/api/v1/workspaces", json={"name": "Normal Name"}, headers=owner_headers
    )
    ws_id = ws_res.json()["data"]["id"]

    # Name with 101 characters -> 422
    res = await async_client.patch(
        f"/api/v1/workspaces/{ws_id}",
        json={"name": "a" * 101},
        headers=owner_headers,
    )
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_update_and_delete_workspace_unauthenticated(async_client: AsyncClient) -> None:
    """Integration test: PATCH and DELETE /api/v1/workspaces/{id} without token -> 401."""
    fake_id = str(uuid4())

    res_patch = await async_client.patch(
        f"/api/v1/workspaces/{fake_id}",
        json={"name": "Unauthorized Change"},
    )
    assert res_patch.status_code == 401
    assert res_patch.json()["error"]["code"] == "UNAUTHORIZED"

    res_delete = await async_client.delete(f"/api/v1/workspaces/{fake_id}")
    assert res_delete.status_code == 401
    assert res_delete.json()["error"]["code"] == "UNAUTHORIZED"


@pytest.mark.asyncio
async def test_delete_workspace_api_cascade_db_level(async_client: AsyncClient) -> None:
    """Integration test: Direct DB verification of cascade deletion of projects and members."""
    from uuid import UUID

    from sqlalchemy import select

    from app.core.database import AsyncSessionLocal
    from app.models.project import Project
    from app.models.user import User
    from app.models.workspace import Workspace, WorkspaceMember

    owner_email = f"db_cascade_owner_{uuid4().hex[:8]}@taskhub.io"
    password = "Password123!"

    # 1. Register Owner
    reg_res = await async_client.post(
        "/api/v1/auth/register",
        json={"email": owner_email, "full_name": "Cascade Owner", "password": password},
    )
    owner_user_id = UUID(reg_res.json()["data"]["id"])

    login_res = await async_client.post(
        "/api/v1/auth/login", json={"email": owner_email, "password": password}
    )
    owner_headers = {"Authorization": f"Bearer {login_res.json()['data']['access_token']}"}

    # 2. Create Workspace
    ws_res = await async_client.post(
        "/api/v1/workspaces", json={"name": "Cascade DB Workspace"}, headers=owner_headers
    )
    ws_id = UUID(ws_res.json()["data"]["id"])

    # 3. Create a Project directly in DB belonging to this workspace
    async with AsyncSessionLocal() as session:
        project = Project(workspace_id=ws_id, name="Test Cascade Project")
        session.add(project)
        await session.commit()
        project_id = project.id

    # 4. Perform DELETE workspace API call
    delete_res = await async_client.delete(
        f"/api/v1/workspaces/{ws_id}",
        headers=owner_headers,
    )
    assert delete_res.status_code == 204

    # 5. Query DB directly to verify cascade deletion
    async with AsyncSessionLocal() as session:
        # Workspace must be deleted
        ws_in_db = (
            await session.execute(select(Workspace).where(Workspace.id == ws_id))
        ).scalar_one_or_none()
        assert ws_in_db is None

        # Projects of workspace must be deleted
        proj_in_db = (
            await session.execute(select(Project).where(Project.id == project_id))
        ).scalar_one_or_none()
        assert proj_in_db is None

        # WorkspaceMembers of workspace must be deleted
        members_in_db = (
            await session.execute(
                select(WorkspaceMember).where(WorkspaceMember.workspace_id == ws_id)
            )
        ).scalars().all()
        assert len(members_in_db) == 0

        # Owner User entity MUST remain intact
        owner_in_db = (
            await session.execute(select(User).where(User.id == owner_user_id))
        ).scalar_one_or_none()
        assert owner_in_db is not None
        assert owner_in_db.email == owner_email


