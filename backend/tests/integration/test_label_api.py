from uuid import UUID, uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings
from app.models.enums import WorkspaceRole
from app.models.label import Label
from app.models.project import Project
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
    session_factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
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


async def _create_project_in_db(workspace_id: UUID, name: str = "Test Project") -> Project:
    """Helper to create a project in the database."""
    engine = create_async_engine(settings.DATABASE_URL)
    session_factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        proj = Project(workspace_id=workspace_id, name=name)
        session.add(proj)
        await session.commit()
        proj_id = proj.id
        proj_name = proj.name
    await engine.dispose()
    return Project(id=proj_id, workspace_id=workspace_id, name=proj_name)


async def _create_label_in_db(project_id: UUID, name: str, color: str = "#EF4444") -> Label:
    """Helper to insert a label directly in the database."""
    engine = create_async_engine(settings.DATABASE_URL)
    session_factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        lbl = Label(project_id=project_id, name=name, color=color)
        session.add(lbl)
        await session.commit()
        lbl_id = lbl.id
    await engine.dispose()
    return Label(id=lbl_id, project_id=project_id, name=name, color=color)


@pytest.mark.asyncio
async def test_create_label_owner_success(async_client: AsyncClient) -> None:
    """Integration test: OWNER creates a label successfully -> 201 Created."""
    headers, owner_id = await _create_test_user(async_client, prefix="owner")
    workspace = await _create_workspace_with_member(owner_id=owner_id)
    project = await _create_project_in_db(workspace_id=workspace.id)

    payload = {"name": "Bug", "color": "#EF4444"}
    res = await async_client.post(
        f"/api/v1/projects/{project.id}/labels",
        json=payload,
        headers=headers,
    )

    assert res.status_code == 201
    data = res.json()["data"]
    assert data["name"] == "Bug"
    assert data["color"] == "#EF4444"
    assert data["project_id"] == str(project.id)


@pytest.mark.asyncio
async def test_create_label_editor_success(async_client: AsyncClient) -> None:
    """Integration test: EDITOR creates a label successfully -> 201 Created."""
    _owner_headers, owner_id = await _create_test_user(async_client, prefix="owner")
    editor_headers, editor_id = await _create_test_user(async_client, prefix="editor")
    workspace = await _create_workspace_with_member(
        owner_id=owner_id, member_id=editor_id, role=WorkspaceRole.EDITOR
    )
    project = await _create_project_in_db(workspace_id=workspace.id)

    payload = {"name": "Feature", "color": "#3B82F6"}
    res = await async_client.post(
        f"/api/v1/projects/{project.id}/labels",
        json=payload,
        headers=editor_headers,
    )

    assert res.status_code == 201
    assert res.json()["data"]["name"] == "Feature"


@pytest.mark.asyncio
async def test_create_label_viewer_forbidden(async_client: AsyncClient) -> None:
    """Integration test: VIEWER attempting to create label returns 403 Forbidden."""
    _owner_headers, owner_id = await _create_test_user(async_client, prefix="owner")
    viewer_headers, viewer_id = await _create_test_user(async_client, prefix="viewer")
    workspace = await _create_workspace_with_member(
        owner_id=owner_id, member_id=viewer_id, role=WorkspaceRole.VIEWER
    )
    project = await _create_project_in_db(workspace_id=workspace.id)

    payload = {"name": "Documentation", "color": "#10B981"}
    res = await async_client.post(
        f"/api/v1/projects/{project.id}/labels",
        json=payload,
        headers=viewer_headers,
    )

    assert res.status_code == 403
    assert res.json()["error"]["code"] == "FORBIDDEN"


@pytest.mark.asyncio
async def test_create_label_duplicate_conflict(async_client: AsyncClient) -> None:
    """Integration test: Creating label with duplicate name returns 409 Conflict."""
    headers, owner_id = await _create_test_user(async_client, prefix="owner")
    workspace = await _create_workspace_with_member(owner_id=owner_id)
    project = await _create_project_in_db(workspace_id=workspace.id)
    await _create_label_in_db(project_id=project.id, name="Bug", color="#EF4444")

    payload = {"name": "Bug", "color": "#FF0000"}
    res = await async_client.post(
        f"/api/v1/projects/{project.id}/labels",
        json=payload,
        headers=headers,
    )

    assert res.status_code == 409
    assert res.json()["error"]["code"] == "CONFLICT"


@pytest.mark.asyncio
async def test_create_label_invalid_color(async_client: AsyncClient) -> None:
    """Integration test: Creating label with invalid hex color returns 422 Unprocessable Entity."""
    headers, owner_id = await _create_test_user(async_client, prefix="owner")
    workspace = await _create_workspace_with_member(owner_id=owner_id)
    project = await _create_project_in_db(workspace_id=workspace.id)

    invalid_colors = ["123456", "#FFF", "red", "#GGGGGG", "#1234567"]
    for color in invalid_colors:
        payload = {"name": "TestColor", "color": color}
        res = await async_client.post(
            f"/api/v1/projects/{project.id}/labels",
            json=payload,
            headers=headers,
        )
        assert res.status_code in (400, 422)


@pytest.mark.asyncio
async def test_create_label_non_member_idor(async_client: AsyncClient) -> None:
    """Integration test: Non-member creating label returns 404 Not Found (IDOR Guard)."""
    _owner_headers, owner_id = await _create_test_user(async_client, prefix="owner")
    stranger_headers, _stranger_id = await _create_test_user(async_client, prefix="stranger")
    workspace = await _create_workspace_with_member(owner_id=owner_id)
    project = await _create_project_in_db(workspace_id=workspace.id)

    payload = {"name": "Secret", "color": "#000000"}
    res = await async_client.post(
        f"/api/v1/projects/{project.id}/labels",
        json=payload,
        headers=stranger_headers,
    )

    assert res.status_code == 404
    assert res.json()["error"]["code"] == "NOT_FOUND"


@pytest.mark.asyncio
async def test_list_labels_success(async_client: AsyncClient) -> None:
    """Integration test: Workspace members (e.g. VIEWER) can list labels -> 200 OK."""
    _owner_headers, owner_id = await _create_test_user(async_client, prefix="owner")
    viewer_headers, viewer_id = await _create_test_user(async_client, prefix="viewer")
    workspace = await _create_workspace_with_member(
        owner_id=owner_id, member_id=viewer_id, role=WorkspaceRole.VIEWER
    )
    project = await _create_project_in_db(workspace_id=workspace.id)

    await _create_label_in_db(project_id=project.id, name="Bug", color="#EF4444")
    await _create_label_in_db(project_id=project.id, name="Feature", color="#3B82F6")

    res = await async_client.get(
        f"/api/v1/projects/{project.id}/labels",
        headers=viewer_headers,
    )

    assert res.status_code == 200
    data = res.json()["data"]
    assert len(data) == 2
    # Sorted by name ascending: Bug, Feature
    assert data[0]["name"] == "Bug"
    assert data[1]["name"] == "Feature"


@pytest.mark.asyncio
async def test_list_labels_non_member_idor(async_client: AsyncClient) -> None:
    """Integration test: Non-member listing labels returns 404 Not Found (IDOR Guard)."""
    _owner_headers, owner_id = await _create_test_user(async_client, prefix="owner")
    stranger_headers, _stranger_id = await _create_test_user(async_client, prefix="stranger")
    workspace = await _create_workspace_with_member(owner_id=owner_id)
    project = await _create_project_in_db(workspace_id=workspace.id)

    res = await async_client.get(
        f"/api/v1/projects/{project.id}/labels",
        headers=stranger_headers,
    )

    assert res.status_code == 404
    assert res.json()["error"]["code"] == "NOT_FOUND"
