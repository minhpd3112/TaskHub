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


@pytest.mark.asyncio
async def test_create_task_api_success(async_client: AsyncClient) -> None:
    """Integration test: OWNER creates a task -> 201 Created with valid payload."""
    owner_headers, owner_id = await _create_test_user(async_client, prefix="task_owner")
    _, assignee_id = await _create_test_user(async_client, prefix="task_assignee")

    workspace = await _create_workspace_with_member(
        owner_id=owner_id,
        member_id=assignee_id,
        role=WorkspaceRole.EDITOR,
    )

    # Create project first
    proj_res = await async_client.post(
        f"/api/v1/workspaces/{workspace.id}/projects",
        json={"name": "Task Test Project"},
        headers=owner_headers,
    )
    assert proj_res.status_code == 201
    project_id = proj_res.json()["data"]["id"]

    # Create task
    task_payload = {
        "title": "Thiết kế màn hình login",
        "description": "Thiết kế theo Figma đã được approve",
        "status": "TODO",
        "priority": "HIGH",
        "due_date": "2026-02-01",
        "assignee_id": str(assignee_id),
    }

    response = await async_client.post(
        f"/api/v1/projects/{project_id}/tasks",
        json=task_payload,
        headers=owner_headers,
    )

    assert response.status_code == 201
    data = response.json()["data"]
    assert data["title"] == "Thiết kế màn hình login"
    assert data["description"] == "Thiết kế theo Figma đã được approve"
    assert data["status"] == "TODO"
    assert data["priority"] == "HIGH"
    assert data["due_date"] == "2026-02-01"
    assert data["assignee_id"] == str(assignee_id)
    assert data["created_by"] == str(owner_id)
    assert data["assignee"]["id"] == str(assignee_id)
    assert "email" in data["assignee"]
    assert data["labels"] == []
    assert "id" in data
    assert "created_at" in data


@pytest.mark.asyncio
async def test_create_task_api_as_viewer_forbidden(async_client: AsyncClient) -> None:
    """Integration test: VIEWER attempts to create task -> 403 Forbidden."""
    owner_headers, owner_id = await _create_test_user(async_client, prefix="tw_owner")
    viewer_headers, viewer_id = await _create_test_user(async_client, prefix="tw_viewer")

    workspace = await _create_workspace_with_member(
        owner_id=owner_id,
        member_id=viewer_id,
        role=WorkspaceRole.VIEWER,
    )

    proj_res = await async_client.post(
        f"/api/v1/workspaces/{workspace.id}/projects",
        json={"name": "Viewer Task Proj"},
        headers=owner_headers,
    )
    assert proj_res.status_code == 201
    project_id = proj_res.json()["data"]["id"]

    # VIEWER calling create_task
    response = await async_client.post(
        f"/api/v1/projects/{project_id}/tasks",
        json={"title": "Viewer Task", "assignee_id": str(viewer_id)},
        headers=viewer_headers,
    )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "FORBIDDEN"


@pytest.mark.asyncio
async def test_create_task_api_invalid_assignee_not_in_workspace(
    async_client: AsyncClient,
) -> None:
    """Integration test: assignee_id not in workspace -> 400 Bad Request."""
    owner_headers, owner_id = await _create_test_user(async_client, prefix="ass_owner")
    _, outsider_id = await _create_test_user(async_client, prefix="ass_outsider")

    workspace = await _create_workspace_with_member(owner_id=owner_id)

    proj_res = await async_client.post(
        f"/api/v1/workspaces/{workspace.id}/projects",
        json={"name": "Assignee Validation Project"},
        headers=owner_headers,
    )
    assert proj_res.status_code == 201
    project_id = proj_res.json()["data"]["id"]

    task_payload = {
        "title": "Task for outsider",
        "assignee_id": str(outsider_id),
    }

    response = await async_client.post(
        f"/api/v1/projects/{project_id}/tasks",
        json=task_payload,
        headers=owner_headers,
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "INVALID_ASSIGNEE"


@pytest.mark.asyncio
async def test_create_task_api_unauthorized(async_client: AsyncClient) -> None:
    """Integration test: Request without Authorization token -> 401 Unauthorized."""
    response = await async_client.post(
        f"/api/v1/projects/{uuid4()}/tasks",
        json={"title": "No Auth Task", "assignee_id": str(uuid4())},
    )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHORIZED"


@pytest.mark.asyncio
async def test_create_task_api_project_not_found(async_client: AsyncClient) -> None:
    """Integration test: Non-existent project_id -> 404 Not Found."""
    headers, user_id = await _create_test_user(async_client, prefix="nf_task_user")
    fake_project_id = uuid4()

    response = await async_client.post(
        f"/api/v1/projects/{fake_project_id}/tasks",
        json={"title": "Task for fake project", "assignee_id": str(user_id)},
        headers=headers,
    )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"


@pytest.mark.asyncio
async def test_create_task_api_non_member_404(async_client: AsyncClient) -> None:
    """Integration test: User from another workspace creating task -> 404 Not Found (IDOR Guard)."""
    owner_headers, owner_id = await _create_test_user(async_client, prefix="nm_task_owner")
    outsider_headers, _ = await _create_test_user(async_client, prefix="nm_task_outsider")

    workspace = await _create_workspace_with_member(owner_id=owner_id)

    proj_res = await async_client.post(
        f"/api/v1/workspaces/{workspace.id}/projects",
        json={"name": "Protected Project for Tasks"},
        headers=owner_headers,
    )
    assert proj_res.status_code == 201
    project_id = proj_res.json()["data"]["id"]

    response = await async_client.post(
        f"/api/v1/projects/{project_id}/tasks",
        json={"title": "Unauthorized Task Creation", "assignee_id": str(owner_id)},
        headers=outsider_headers,
    )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"


@pytest.mark.asyncio
async def test_create_task_api_archived_project_fails(async_client: AsyncClient) -> None:
    """Integration test: Creating task in ARCHIVED project -> 400 (PROJECT_ARCHIVED)."""
    owner_headers, owner_id = await _create_test_user(async_client, prefix="arch_task_owner")
    workspace = await _create_workspace_with_member(owner_id=owner_id)

    # 1. Create project
    proj_res = await async_client.post(
        f"/api/v1/workspaces/{workspace.id}/projects",
        json={"name": "Project to be archived"},
        headers=owner_headers,
    )
    assert proj_res.status_code == 201
    project_id = proj_res.json()["data"]["id"]

    # 2. Archive project
    archive_res = await async_client.patch(
        f"/api/v1/projects/{project_id}/archive",
        headers=owner_headers,
    )
    assert archive_res.status_code == 200
    assert archive_res.json()["data"]["status"] == "ARCHIVED"

    # 3. Attempt to create task in archived project
    response = await async_client.post(
        f"/api/v1/projects/{project_id}/tasks",
        json={"title": "Task in Archived Project", "assignee_id": str(owner_id)},
        headers=owner_headers,
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "PROJECT_ARCHIVED"


@pytest.mark.asyncio
async def test_list_tasks_api_success(async_client: AsyncClient) -> None:
    """Integration test: List tasks with pagination and status/priority filters."""
    owner_headers, owner_id = await _create_test_user(async_client, prefix="list_owner")
    workspace = await _create_workspace_with_member(owner_id=owner_id)

    # 1. Create project
    proj_res = await async_client.post(
        f"/api/v1/workspaces/{workspace.id}/projects",
        json={"name": "List Tasks Project"},
        headers=owner_headers,
    )
    assert proj_res.status_code == 201
    project_id = proj_res.json()["data"]["id"]

    # 2. Create 2 tasks
    await async_client.post(
        f"/api/v1/projects/{project_id}/tasks",
        json={
            "title": "Task 1 TODO HIGH",
            "status": "TODO",
            "priority": "HIGH",
            "assignee_id": str(owner_id),
        },
        headers=owner_headers,
    )
    await async_client.post(
        f"/api/v1/projects/{project_id}/tasks",
        json={
            "title": "Task 2 IN_PROGRESS LOW",
            "status": "IN_PROGRESS",
            "priority": "LOW",
            "assignee_id": str(owner_id),
        },
        headers=owner_headers,
    )

    # 3. List all tasks
    res = await async_client.get(
        f"/api/v1/projects/{project_id}/tasks?page=1&limit=10",
        headers=owner_headers,
    )
    assert res.status_code == 200
    body = res.json()
    assert "data" in body
    assert "pagination" in body
    assert body["pagination"]["total"] == 2
    assert len(body["data"]) == 2

    # 4. Filter by status=TODO
    res_todo = await async_client.get(
        f"/api/v1/projects/{project_id}/tasks?status=TODO",
        headers=owner_headers,
    )
    assert res_todo.status_code == 200
    todo_body = res_todo.json()
    assert todo_body["pagination"]["total"] == 1
    assert todo_body["data"][0]["status"] == "TODO"

    # 5. Filter by priority=LOW
    res_low = await async_client.get(
        f"/api/v1/projects/{project_id}/tasks?priority=LOW",
        headers=owner_headers,
    )
    assert res_low.status_code == 200
    low_body = res_low.json()
    assert low_body["pagination"]["total"] == 1
    assert low_body["data"][0]["priority"] == "LOW"


@pytest.mark.asyncio
async def test_list_tasks_api_editor_scoped(async_client: AsyncClient) -> None:
    """Integration test: EDITOR only lists tasks assigned to themselves."""
    owner_headers, owner_id = await _create_test_user(async_client, prefix="scoped_owner")
    editor_headers, editor_id = await _create_test_user(async_client, prefix="scoped_editor")

    workspace = await _create_workspace_with_member(
        owner_id=owner_id,
        member_id=editor_id,
        role=WorkspaceRole.EDITOR,
    )

    proj_res = await async_client.post(
        f"/api/v1/workspaces/{workspace.id}/projects",
        json={"name": "Scoped Visibility Project"},
        headers=owner_headers,
    )
    assert proj_res.status_code == 201
    project_id = proj_res.json()["data"]["id"]

    # Task assigned to Owner
    await async_client.post(
        f"/api/v1/projects/{project_id}/tasks",
        json={"title": "Owner's Task", "assignee_id": str(owner_id)},
        headers=owner_headers,
    )

    # Task assigned to Editor
    await async_client.post(
        f"/api/v1/projects/{project_id}/tasks",
        json={"title": "Editor's Task", "assignee_id": str(editor_id)},
        headers=owner_headers,
    )

    # Editor requests tasks list
    res = await async_client.get(
        f"/api/v1/projects/{project_id}/tasks",
        headers=editor_headers,
    )
    assert res.status_code == 200
    body = res.json()
    assert body["pagination"]["total"] == 1
    assert body["data"][0]["title"] == "Editor's Task"
    assert body["data"][0]["assignee_id"] == str(editor_id)


@pytest.mark.asyncio
async def test_list_tasks_api_non_member_404(async_client: AsyncClient) -> None:
    """Integration test: Non-workspace member listing tasks -> 404 NOT_FOUND."""
    owner_headers, owner_id = await _create_test_user(async_client, prefix="nm_list_owner")
    outsider_headers, _ = await _create_test_user(async_client, prefix="nm_list_outsider")

    workspace = await _create_workspace_with_member(owner_id=owner_id)

    proj_res = await async_client.post(
        f"/api/v1/workspaces/{workspace.id}/projects",
        json={"name": "Private List Project"},
        headers=owner_headers,
    )
    assert proj_res.status_code == 201
    project_id = proj_res.json()["data"]["id"]

    res = await async_client.get(
        f"/api/v1/projects/{project_id}/tasks",
        headers=outsider_headers,
    )
    assert res.status_code == 404
    assert res.json()["error"]["code"] == "NOT_FOUND"


@pytest.mark.asyncio
async def test_get_task_detail_api_success(async_client: AsyncClient) -> None:
    """Integration test: GET /api/v1/tasks/{task_id} returns detailed task."""
    owner_headers, owner_id = await _create_test_user(async_client, prefix="detail_owner")
    workspace = await _create_workspace_with_member(owner_id=owner_id)

    proj_res = await async_client.post(
        f"/api/v1/workspaces/{workspace.id}/projects",
        json={"name": "Detail Task Project"},
        headers=owner_headers,
    )
    project_id = proj_res.json()["data"]["id"]

    task_res = await async_client.post(
        f"/api/v1/projects/{project_id}/tasks",
        json={
            "title": "Task for Detail Test",
            "description": "Comprehensive description",
            "assignee_id": str(owner_id),
        },
        headers=owner_headers,
    )
    task_id = task_res.json()["data"]["id"]

    res = await async_client.get(
        f"/api/v1/tasks/{task_id}",
        headers=owner_headers,
    )
    assert res.status_code == 200
    data = res.json()["data"]
    assert data["id"] == task_id
    assert data["title"] == "Task for Detail Test"
    assert data["description"] == "Comprehensive description"
    assert data["assignee"]["id"] == str(owner_id)
    assert data["creator"]["id"] == str(owner_id)
    assert "labels" in data
    assert "comments" in data


@pytest.mark.asyncio
async def test_get_task_detail_api_editor_other_task_404(async_client: AsyncClient) -> None:
    """Integration test: EDITOR accessing task assigned to someone else -> 404 NOT_FOUND."""
    owner_headers, owner_id = await _create_test_user(async_client, prefix="ed_det_owner")
    editor_headers, editor_id = await _create_test_user(async_client, prefix="ed_det_editor")

    workspace = await _create_workspace_with_member(
        owner_id=owner_id,
        member_id=editor_id,
        role=WorkspaceRole.EDITOR,
    )

    proj_res = await async_client.post(
        f"/api/v1/workspaces/{workspace.id}/projects",
        json={"name": "Editor Detail Project"},
        headers=owner_headers,
    )
    project_id = proj_res.json()["data"]["id"]

    # Task assigned to Owner
    task_res = await async_client.post(
        f"/api/v1/projects/{project_id}/tasks",
        json={"title": "Owner Only Task", "assignee_id": str(owner_id)},
        headers=owner_headers,
    )
    task_id = task_res.json()["data"]["id"]

    # Editor tries to view Owner's task
    res = await async_client.get(
        f"/api/v1/tasks/{task_id}",
        headers=editor_headers,
    )
    assert res.status_code == 404
    assert res.json()["error"]["code"] == "NOT_FOUND"
