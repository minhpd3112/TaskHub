from uuid import UUID, uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings
from app.models.enums import WorkspaceRole
from app.models.workspace import Workspace, WorkspaceMember


async def _create_test_user(
    async_client: AsyncClient, prefix: str = "user"
) -> tuple[dict[str, str], UUID]:
    """Helper to register and login a new user, returning headers and user_id."""
    email = f"{prefix}_{uuid4().hex[:8]}@taskhub.io"
    password = "Password123!"
    reg_res = await async_client.post(
        "/api/v1/auth/register",
        json={"email": email, "full_name": f"Test {prefix}", "password": password},
    )
    user_id = UUID(reg_res.json()["data"]["id"])

    login_res = await async_client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    access_token = login_res.json()["data"]["access_token"]
    headers = {"Authorization": f"Bearer {access_token}"}
    return headers, user_id


async def _create_workspace_with_member(

    owner_id: UUID,
    member_id: UUID | None = None,
    role: WorkspaceRole = WorkspaceRole.OWNER,
) -> Workspace:
    """Helper to create a workspace and add a member with specific role."""
    engine = create_async_engine(settings.DATABASE_URL)
    session_factory = async_sessionmaker(
        bind=engine, class_=AsyncSession, expire_on_commit=False
    )
    async with session_factory() as session:
        ws = Workspace(name=f"Workspace-{uuid4().hex[:6]}", owner_id=owner_id)
        session.add(ws)
        await session.flush()

        owner_member = WorkspaceMember(
            workspace_id=ws.id, user_id=owner_id, role=WorkspaceRole.OWNER
        )
        session.add(owner_member)

        if member_id and member_id != owner_id:
            member = WorkspaceMember(workspace_id=ws.id, user_id=member_id, role=role)
            session.add(member)

        await session.commit()
        ws_id = ws.id
        ws_name = ws.name

    await engine.dispose()
    return Workspace(id=ws_id, name=ws_name, owner_id=owner_id)





@pytest.mark.asyncio
async def test_create_project_as_owner_success(async_client: AsyncClient) -> None:
    """Integration test: OWNER creates a project -> 201 Created with ACTIVE status."""
    headers, user_id = await _create_test_user(async_client, prefix="owner")
    workspace = await _create_workspace_with_member(owner_id=user_id)

    payload = {
        "name": "Website Redesign",
        "description": "Thiết kế lại giao diện website công ty",
    }

    response = await async_client.post(
        f"/api/v1/workspaces/{workspace.id}/projects",
        json=payload,
        headers=headers,
    )

    assert response.status_code == 201
    data = response.json()["data"]
    assert data["name"] == "Website Redesign"
    assert data["description"] == "Thiết kế lại giao diện website công ty"
    assert data["workspace_id"] == str(workspace.id)
    assert data["status"] == "ACTIVE"
    assert "id" in data
    assert "created_at" in data


@pytest.mark.asyncio
async def test_create_project_as_editor_success(async_client: AsyncClient) -> None:
    """Integration test: EDITOR creates a project -> 201 Created."""
    owner_headers, owner_id = await _create_test_user(async_client, prefix="owner")
    editor_headers, editor_id = await _create_test_user(async_client, prefix="editor")

    workspace = await _create_workspace_with_member(
        owner_id=owner_id,
        member_id=editor_id,
        role=WorkspaceRole.EDITOR,
    )

    payload = {"name": "Editor Project"}

    response = await async_client.post(
        f"/api/v1/workspaces/{workspace.id}/projects",
        json=payload,
        headers=editor_headers,
    )

    assert response.status_code == 201
    data = response.json()["data"]
    assert data["name"] == "Editor Project"
    assert data["description"] is None
    assert data["status"] == "ACTIVE"


@pytest.mark.asyncio
async def test_create_project_as_viewer_forbidden(async_client: AsyncClient) -> None:
    """Integration test: VIEWER attempts to create a project -> 403 Forbidden."""
    _, owner_id = await _create_test_user(async_client, prefix="owner")
    viewer_headers, viewer_id = await _create_test_user(async_client, prefix="viewer")

    workspace = await _create_workspace_with_member(
        owner_id=owner_id,
        member_id=viewer_id,
        role=WorkspaceRole.VIEWER,
    )

    response = await async_client.post(
        f"/api/v1/workspaces/{workspace.id}/projects",
        json={"name": "Viewer Forbidden Project"},
        headers=viewer_headers,
    )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "FORBIDDEN"


@pytest.mark.asyncio
async def test_create_project_non_member_forbidden(async_client: AsyncClient) -> None:
    """Integration test: Non-member attempts to create a project -> 403 Forbidden."""
    _, owner_id = await _create_test_user(async_client, prefix="owner")
    outsider_headers, _ = await _create_test_user(async_client, prefix="outsider")

    workspace = await _create_workspace_with_member(owner_id=owner_id)

    response = await async_client.post(
        f"/api/v1/workspaces/{workspace.id}/projects",
        json={"name": "Outsider Project"},
        headers=outsider_headers,
    )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "FORBIDDEN"


@pytest.mark.asyncio
async def test_create_project_validation_empty_name(async_client: AsyncClient) -> None:
    """Integration test: Empty or whitespace name -> 422 Unprocessable Entity."""
    headers, user_id = await _create_test_user(async_client, prefix="val_user")
    workspace = await _create_workspace_with_member(owner_id=user_id)

    response = await async_client.post(
        f"/api/v1/workspaces/{workspace.id}/projects",
        json={"name": "   "},
        headers=headers,
    )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_create_project_validation_name_too_long(async_client: AsyncClient) -> None:
    """Integration test: Name > 200 chars -> 422 Unprocessable Entity."""
    headers, user_id = await _create_test_user(async_client, prefix="val_user2")
    workspace = await _create_workspace_with_member(owner_id=user_id)

    response = await async_client.post(
        f"/api/v1/workspaces/{workspace.id}/projects",
        json={"name": "A" * 201},
        headers=headers,
    )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_create_project_workspace_not_found(async_client: AsyncClient) -> None:
    """Integration test: Non-existent workspace UUID -> 404 Not Found."""
    headers, _ = await _create_test_user(async_client, prefix="nf_user")
    fake_workspace_id = uuid4()

    response = await async_client.post(
        f"/api/v1/workspaces/{fake_workspace_id}/projects",
        json={"name": "Valid Name"},
        headers=headers,
    )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"


@pytest.mark.asyncio
async def test_create_project_unauthorized(async_client: AsyncClient) -> None:
    """Integration test: Missing token -> 401 Unauthorized."""
    fake_workspace_id = uuid4()
    response = await async_client.post(
        f"/api/v1/workspaces/{fake_workspace_id}/projects",
        json={"name": "No Token Project"},
    )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHORIZED"
