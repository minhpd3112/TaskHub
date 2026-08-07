from uuid import UUID, uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings
from app.models.enums import ProjectStatus, WorkspaceRole
from app.models.project import Project
from app.models.task import Task
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


async def _create_project_in_db(
    workspace_id: UUID,
    name: str = "Test Project",
    status: ProjectStatus = ProjectStatus.ACTIVE,
) -> Project:
    """Helper to create a project in the database."""
    engine = create_async_engine(settings.DATABASE_URL)
    session_factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        proj = Project(workspace_id=workspace_id, name=name, status=status)
        session.add(proj)
        await session.commit()
        proj_id = proj.id
        proj_name = proj.name
        proj_status = proj.status
    await engine.dispose()
    return Project(id=proj_id, workspace_id=workspace_id, name=proj_name, status=proj_status)


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
async def test_create_project_as_editor_forbidden(async_client: AsyncClient) -> None:
    """Integration test: EDITOR attempts to create a project -> 403 Forbidden."""
    owner_headers, owner_id = await _create_test_user(async_client, prefix="owner_ed")
    editor_headers, editor_id = await _create_test_user(async_client, prefix="editor_ed")

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

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "FORBIDDEN"


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


@pytest.mark.asyncio
async def test_list_projects_api_success(async_client: AsyncClient) -> None:
    """Integration test: Workspace VIEWER/EDITOR/OWNER lists projects successfully."""
    owner_headers, owner_id = await _create_test_user(async_client, prefix="list_owner")
    viewer_headers, viewer_id = await _create_test_user(async_client, prefix="list_viewer")
    workspace = await _create_workspace_with_member(
        owner_id=owner_id, member_id=viewer_id, role=WorkspaceRole.VIEWER
    )

    await _create_project_in_db(workspace.id, name="Project Alpha")
    await _create_project_in_db(workspace.id, name="Project Beta")

    response = await async_client.get(
        f"/api/v1/workspaces/{workspace.id}/projects",
        headers=viewer_headers,
    )

    assert response.status_code == 200
    res_data = response.json()
    assert len(res_data["data"]) == 2
    assert res_data["pagination"]["total"] == 2
    assert res_data["pagination"]["page"] == 1


@pytest.mark.asyncio
async def test_list_projects_api_filter_status(async_client: AsyncClient) -> None:
    """Integration test: Filtering projects by status ACTIVE / ARCHIVED."""
    headers, user_id = await _create_test_user(async_client, prefix="filter_user")
    workspace = await _create_workspace_with_member(owner_id=user_id)

    await _create_project_in_db(workspace.id, name="Active 1", status=ProjectStatus.ACTIVE)
    await _create_project_in_db(workspace.id, name="Archived 1", status=ProjectStatus.ARCHIVED)

    res_active = await async_client.get(
        f"/api/v1/workspaces/{workspace.id}/projects?status=ACTIVE",
        headers=headers,
    )
    assert res_active.status_code == 200
    assert len(res_active.json()["data"]) == 1
    assert res_active.json()["data"][0]["status"] == "ACTIVE"

    res_archived = await async_client.get(
        f"/api/v1/workspaces/{workspace.id}/projects?status=ARCHIVED",
        headers=headers,
    )
    assert res_archived.status_code == 200
    assert len(res_archived.json()["data"]) == 1
    assert res_archived.json()["data"][0]["status"] == "ARCHIVED"


@pytest.mark.asyncio
async def test_list_projects_api_pagination(async_client: AsyncClient) -> None:
    """Integration test: Pagination limit and page params."""
    headers, user_id = await _create_test_user(async_client, prefix="page_user")
    workspace = await _create_workspace_with_member(owner_id=user_id)

    for i in range(3):
        await _create_project_in_db(workspace.id, name=f"Proj {i}")

    response = await async_client.get(
        f"/api/v1/workspaces/{workspace.id}/projects?page=1&limit=2",
        headers=headers,
    )
    assert response.status_code == 200
    res_json = response.json()
    assert len(res_json["data"]) == 2
    assert res_json["pagination"]["total"] == 3
    assert res_json["pagination"]["total_pages"] == 2


@pytest.mark.asyncio
async def test_list_projects_api_non_member_404(async_client: AsyncClient) -> None:
    """Integration test: Non-member attempting to list workspace projects -> 404 Not Found."""
    _, owner_id = await _create_test_user(async_client, prefix="owner_nm")
    outsider_headers, _ = await _create_test_user(async_client, prefix="outsider_nm")
    workspace = await _create_workspace_with_member(owner_id=owner_id)

    response = await async_client.get(
        f"/api/v1/workspaces/{workspace.id}/projects",
        headers=outsider_headers,
    )
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"


@pytest.mark.asyncio
async def test_get_project_api_success(async_client: AsyncClient) -> None:
    """Integration test: GET /api/v1/projects/{project_id} returns 200 OK with task_count."""
    headers, user_id = await _create_test_user(async_client, prefix="get_user")
    workspace = await _create_workspace_with_member(owner_id=user_id)
    project = await _create_project_in_db(workspace.id, name="Detailed Proj")

    response = await async_client.get(
        f"/api/v1/projects/{project.id}",
        headers=headers,
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["id"] == str(project.id)
    assert data["name"] == "Detailed Proj"
    assert data["task_count"] == 0


@pytest.mark.asyncio
async def test_get_project_api_non_member_404(async_client: AsyncClient) -> None:
    """Integration test: Non-member getting project detail returns 404 NOT_FOUND."""
    _, owner_id = await _create_test_user(async_client, prefix="owner_idor")
    outsider_headers, _ = await _create_test_user(async_client, prefix="outsider_idor")
    workspace = await _create_workspace_with_member(owner_id=owner_id)
    project = await _create_project_in_db(workspace.id, name="Protected Proj")

    response = await async_client.get(
        f"/api/v1/projects/{project.id}",
        headers=outsider_headers,
    )
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"


@pytest.mark.asyncio
async def test_get_project_detail_api_editor_with_task_success(
    async_client: AsyncClient,
) -> None:
    """Integration test: EDITOR with assigned task in project gets 200 OK."""
    _, owner_id = await _create_test_user(async_client, prefix="get_ed_owner")
    editor_headers, editor_id = await _create_test_user(async_client, prefix="get_ed_user")
    workspace = await _create_workspace_with_member(
        owner_id=owner_id, member_id=editor_id, role=WorkspaceRole.EDITOR
    )
    project = await _create_project_in_db(workspace.id, name="Editor Task Proj")
    await _create_task_in_db(project.id, editor_id, title="Assigned to Editor")

    response = await async_client.get(
        f"/api/v1/projects/{project.id}",
        headers=editor_headers,
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["id"] == str(project.id)
    assert data["name"] == "Editor Task Proj"
    assert data["task_count"] == 1


@pytest.mark.asyncio
async def test_get_project_detail_api_editor_without_task_not_found(
    async_client: AsyncClient,
) -> None:
    """Integration test: EDITOR without assigned task in project gets 404 NOT_FOUND."""
    _, owner_id = await _create_test_user(async_client, prefix="get_ed_owner2")
    editor_headers, editor_id = await _create_test_user(async_client, prefix="get_ed_user2")
    workspace = await _create_workspace_with_member(
        owner_id=owner_id, member_id=editor_id, role=WorkspaceRole.EDITOR
    )
    project = await _create_project_in_db(workspace.id, name="Editor No Task Proj")

    response = await async_client.get(
        f"/api/v1/projects/{project.id}",
        headers=editor_headers,
    )
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"


async def _create_task_in_db(
    project_id: UUID,
    user_id: UUID,
    title: str = "Test Task",
) -> Task:
    """Helper to create a task in the database."""
    engine = create_async_engine(settings.DATABASE_URL)
    session_factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        task = Task(
            project_id=project_id,
            assignee_id=user_id,
            created_by=user_id,
            title=title,
        )
        session.add(task)
        await session.commit()
        task_id = task.id
    await engine.dispose()
    return Task(
        id=task_id, project_id=project_id, assignee_id=user_id, created_by=user_id, title=title
    )


@pytest.mark.asyncio
async def test_update_project_api_success(async_client: AsyncClient) -> None:
    """Integration test: PATCH /api/v1/projects/{project_id} updates project -> 200 OK."""
    headers, user_id = await _create_test_user(async_client, prefix="upd_owner")
    workspace = await _create_workspace_with_member(owner_id=user_id)
    project = await _create_project_in_db(workspace.id, name="Original Name")

    payload = {"name": "Updated Project Name", "description": "Updated Description"}
    response = await async_client.patch(
        f"/api/v1/projects/{project.id}",
        json=payload,
        headers=headers,
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["id"] == str(project.id)
    assert data["name"] == "Updated Project Name"
    assert data["description"] == "Updated Description"


@pytest.mark.asyncio
async def test_update_project_api_forbidden_for_editor(async_client: AsyncClient) -> None:
    """Integration test: EDITOR attempting to update project -> 403 Forbidden."""
    _, owner_id = await _create_test_user(async_client, prefix="upd_owner_e")
    editor_headers, editor_id = await _create_test_user(async_client, prefix="upd_editor")
    workspace = await _create_workspace_with_member(
        owner_id=owner_id, member_id=editor_id, role=WorkspaceRole.EDITOR
    )
    project = await _create_project_in_db(workspace.id, name="Project E")

    response = await async_client.patch(
        f"/api/v1/projects/{project.id}",
        json={"name": "Forbidden Change"},
        headers=editor_headers,
    )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "FORBIDDEN"


@pytest.mark.asyncio
async def test_update_project_api_forbidden_for_viewer(async_client: AsyncClient) -> None:
    """Integration test: VIEWER attempting to update project -> 403 Forbidden."""
    _, owner_id = await _create_test_user(async_client, prefix="upd_owner_v")
    viewer_headers, viewer_id = await _create_test_user(async_client, prefix="upd_viewer")
    workspace = await _create_workspace_with_member(
        owner_id=owner_id, member_id=viewer_id, role=WorkspaceRole.VIEWER
    )
    project = await _create_project_in_db(workspace.id, name="Project V")

    response = await async_client.patch(
        f"/api/v1/projects/{project.id}",
        json={"name": "Forbidden Change"},
        headers=viewer_headers,
    )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "FORBIDDEN"


@pytest.mark.asyncio
async def test_update_project_api_non_member_404(async_client: AsyncClient) -> None:
    """Integration test: Non-member updating project -> 404 Not Found (404 Guard)."""
    _, owner_id = await _create_test_user(async_client, prefix="upd_owner_nm")
    outsider_headers, _ = await _create_test_user(async_client, prefix="upd_outsider")
    workspace = await _create_workspace_with_member(owner_id=owner_id)
    project = await _create_project_in_db(workspace.id, name="Protected Proj")

    response = await async_client.patch(
        f"/api/v1/projects/{project.id}",
        json={"name": "Outsider Change"},
        headers=outsider_headers,
    )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"


@pytest.mark.asyncio
async def test_update_project_api_validation_error(async_client: AsyncClient) -> None:
    """Integration test: Updating project with empty/whitespace name -> 422 Unprocessable Entity."""
    headers, user_id = await _create_test_user(async_client, prefix="upd_val")
    workspace = await _create_workspace_with_member(owner_id=user_id)
    project = await _create_project_in_db(workspace.id, name="Valid Proj")

    response = await async_client.patch(
        f"/api/v1/projects/{project.id}",
        json={"name": "   "},
        headers=headers,
    )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_archive_project_api_success_preserves_tasks(async_client: AsyncClient) -> None:
    """Integration test: Archiving project sets status to ARCHIVED and preserves tasks."""
    headers, user_id = await _create_test_user(async_client, prefix="arch_user")
    workspace = await _create_workspace_with_member(owner_id=user_id)
    project = await _create_project_in_db(workspace.id, name="Project to Archive")
    await _create_task_in_db(project.id, user_id, title="Task in Archived Project")

    # Call archive endpoint
    res_archive = await async_client.patch(
        f"/api/v1/projects/{project.id}/archive",
        headers=headers,
    )
    assert res_archive.status_code == 200
    assert res_archive.json()["data"]["status"] == "ARCHIVED"

    # Verify project detail still works and task_count is preserved
    res_detail = await async_client.get(
        f"/api/v1/projects/{project.id}",
        headers=headers,
    )
    assert res_detail.status_code == 200
    detail_data = res_detail.json()["data"]
    assert detail_data["status"] == "ARCHIVED"
    assert detail_data["task_count"] == 1


@pytest.mark.asyncio
async def test_delete_project_api_success(async_client: AsyncClient) -> None:
    """Integration test: DELETE /api/v1/projects/{project_id} -> 204 No Content."""
    headers, user_id = await _create_test_user(async_client, prefix="del_owner")
    workspace = await _create_workspace_with_member(owner_id=user_id)
    project = await _create_project_in_db(workspace.id, name="Project to Delete")
    task = await _create_task_in_db(project.id, user_id, title="Task to CASCADE delete")

    response = await async_client.delete(
        f"/api/v1/projects/{project.id}",
        headers=headers,
    )

    assert response.status_code == 204

    # Verify CASCADE deletion in DB directly
    from sqlalchemy import select

    engine = create_async_engine(settings.DATABASE_URL)
    session_factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        proj_stmt = select(Project).where(Project.id == project.id)
        task_stmt = select(Task).where(Task.id == task.id)
        db_proj = (await session.execute(proj_stmt)).scalar_one_or_none()
        db_task = (await session.execute(task_stmt)).scalar_one_or_none()

        assert db_proj is None
        assert db_task is None

    await engine.dispose()


@pytest.mark.asyncio
async def test_archive_project_api_forbidden_for_editor(async_client: AsyncClient) -> None:
    """Integration test: EDITOR attempting to archive project -> 403 Forbidden."""
    _, owner_id = await _create_test_user(async_client, prefix="arch_owner_e")
    editor_headers, editor_id = await _create_test_user(async_client, prefix="arch_editor")
    workspace = await _create_workspace_with_member(
        owner_id=owner_id, member_id=editor_id, role=WorkspaceRole.EDITOR
    )
    project = await _create_project_in_db(workspace.id, name="Project Arch E")

    response = await async_client.patch(
        f"/api/v1/projects/{project.id}/archive",
        headers=editor_headers,
    )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "FORBIDDEN"


@pytest.mark.asyncio
async def test_delete_project_api_forbidden_for_editor(async_client: AsyncClient) -> None:
    """Integration test: EDITOR attempting to delete project -> 403 Forbidden."""
    _, owner_id = await _create_test_user(async_client, prefix="del_owner_e")
    editor_headers, editor_id = await _create_test_user(async_client, prefix="del_editor")
    workspace = await _create_workspace_with_member(
        owner_id=owner_id, member_id=editor_id, role=WorkspaceRole.EDITOR
    )
    project = await _create_project_in_db(workspace.id, name="Project Protected From Editor")

    response = await async_client.delete(
        f"/api/v1/projects/{project.id}",
        headers=editor_headers,
    )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "FORBIDDEN"


@pytest.mark.asyncio
async def test_delete_project_api_forbidden_for_viewer(async_client: AsyncClient) -> None:
    """Integration test: VIEWER attempting to delete project -> 403 Forbidden."""
    _, owner_id = await _create_test_user(async_client, prefix="del_owner_v")
    viewer_headers, viewer_id = await _create_test_user(async_client, prefix="del_viewer")
    workspace = await _create_workspace_with_member(
        owner_id=owner_id, member_id=viewer_id, role=WorkspaceRole.VIEWER
    )
    project = await _create_project_in_db(workspace.id, name="Project Protected From Viewer")

    response = await async_client.delete(
        f"/api/v1/projects/{project.id}",
        headers=viewer_headers,
    )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "FORBIDDEN"


@pytest.mark.asyncio
async def test_list_projects_api_editor_sees_only_assigned_projects(
    async_client: AsyncClient,
) -> None:
    """Integration test: EDITOR calling GET /workspaces/{id}/projects sees only projects with assigned tasks."""
    _, owner_id = await _create_test_user(async_client, prefix="lst_ed_owner")
    editor_headers, editor_id = await _create_test_user(async_client, prefix="lst_ed_user")

    workspace = await _create_workspace_with_member(
        owner_id=owner_id, member_id=editor_id, role=WorkspaceRole.EDITOR
    )

    proj_a = await _create_project_in_db(workspace.id, name="Project A (Has Task)")
    await _create_project_in_db(workspace.id, name="Project B (No Task)")

    await _create_task_in_db(proj_a.id, editor_id, title="Editor Task A")

    response = await async_client.get(
        f"/api/v1/workspaces/{workspace.id}/projects",
        headers=editor_headers,
    )

    assert response.status_code == 200
    res_data = response.json()
    items = res_data["data"]
    pagination = res_data["pagination"]

    assert pagination["total"] == 1
    assert len(items) == 1
    assert items[0]["id"] == str(proj_a.id)
    assert items[0]["name"] == "Project A (Has Task)"


@pytest.mark.asyncio
async def test_list_projects_api_owner_sees_all_projects(
    async_client: AsyncClient,
) -> None:
    """Integration test: OWNER calling GET /workspaces/{id}/projects sees all projects."""
    owner_headers, owner_id = await _create_test_user(async_client, prefix="lst_ow_owner")
    _, editor_id = await _create_test_user(async_client, prefix="lst_ow_editor")

    workspace = await _create_workspace_with_member(
        owner_id=owner_id, member_id=editor_id, role=WorkspaceRole.EDITOR
    )

    proj_a = await _create_project_in_db(workspace.id, name="Project A (Has Task)")
    proj_b = await _create_project_in_db(workspace.id, name="Project B (No Task)")

    await _create_task_in_db(proj_a.id, editor_id, title="Editor Task A")

    response = await async_client.get(
        f"/api/v1/workspaces/{workspace.id}/projects",
        headers=owner_headers,
    )

    assert response.status_code == 200
    res_data = response.json()
    items = res_data["data"]
    pagination = res_data["pagination"]

    assert pagination["total"] == 2
    assert len(items) == 2
    item_ids = {item["id"] for item in items}
    assert str(proj_a.id) in item_ids
    assert str(proj_b.id) in item_ids
