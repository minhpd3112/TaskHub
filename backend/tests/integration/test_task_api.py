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


@pytest.mark.asyncio
async def test_update_task_api_success_owner(async_client: AsyncClient) -> None:
    """Integration test: OWNER updates task successfully -> 200 OK."""
    owner_headers, owner_id = await _create_test_user(async_client, prefix="upd_owner")
    _, assignee_id = await _create_test_user(async_client, prefix="upd_assignee")

    workspace = await _create_workspace_with_member(
        owner_id=owner_id,
        member_id=assignee_id,
        role=WorkspaceRole.EDITOR,
    )

    proj_res = await async_client.post(
        f"/api/v1/workspaces/{workspace.id}/projects",
        json={"name": "Update Task Project"},
        headers=owner_headers,
    )
    project_id = proj_res.json()["data"]["id"]

    create_res = await async_client.post(
        f"/api/v1/projects/{project_id}/tasks",
        json={"title": "Initial Task Title", "assignee_id": str(owner_id)},
        headers=owner_headers,
    )
    task_id = create_res.json()["data"]["id"]

    update_payload = {
        "title": "Updated Task Title",
        "description": "Updated Task Description",
        "priority": "URGENT",
        "due_date": "2026-12-31",
        "assignee_id": str(assignee_id),
    }

    patch_res = await async_client.patch(
        f"/api/v1/tasks/{task_id}",
        json=update_payload,
        headers=owner_headers,
    )

    assert patch_res.status_code == 200
    data = patch_res.json()["data"]
    assert data["id"] == task_id
    assert data["title"] == "Updated Task Title"
    assert data["description"] == "Updated Task Description"
    assert data["priority"] == "URGENT"
    assert data["due_date"] == "2026-12-31"
    assert data["assignee_id"] == str(assignee_id)
    assert data["updated_at"] is not None


@pytest.mark.asyncio
async def test_update_task_api_forbidden_editor(async_client: AsyncClient) -> None:
    """Integration test: EDITOR calling PATCH /tasks/{task_id} -> 403 FORBIDDEN."""
    owner_headers, owner_id = await _create_test_user(async_client, prefix="upd_ed_owner")
    editor_headers, editor_id = await _create_test_user(async_client, prefix="upd_ed_editor")

    workspace = await _create_workspace_with_member(
        owner_id=owner_id,
        member_id=editor_id,
        role=WorkspaceRole.EDITOR,
    )

    proj_res = await async_client.post(
        f"/api/v1/workspaces/{workspace.id}/projects",
        json={"name": "Editor Update Project"},
        headers=owner_headers,
    )
    project_id = proj_res.json()["data"]["id"]

    create_res = await async_client.post(
        f"/api/v1/projects/{project_id}/tasks",
        json={"title": "Task Assigned to Editor", "assignee_id": str(editor_id)},
        headers=owner_headers,
    )
    task_id = create_res.json()["data"]["id"]

    # Editor attempts full update
    patch_res = await async_client.patch(
        f"/api/v1/tasks/{task_id}",
        json={"title": "Editor Changed Title"},
        headers=editor_headers,
    )

    assert patch_res.status_code == 403
    assert patch_res.json()["error"]["code"] == "FORBIDDEN"


@pytest.mark.asyncio
async def test_update_task_api_forbidden_viewer(async_client: AsyncClient) -> None:
    """Integration test: VIEWER calling PATCH /tasks/{task_id} -> 403 FORBIDDEN."""
    owner_headers, owner_id = await _create_test_user(async_client, prefix="upd_vw_owner")
    viewer_headers, viewer_id = await _create_test_user(async_client, prefix="upd_vw_viewer")

    workspace = await _create_workspace_with_member(
        owner_id=owner_id,
        member_id=viewer_id,
        role=WorkspaceRole.VIEWER,
    )

    proj_res = await async_client.post(
        f"/api/v1/workspaces/{workspace.id}/projects",
        json={"name": "Viewer Update Project"},
        headers=owner_headers,
    )
    project_id = proj_res.json()["data"]["id"]

    create_res = await async_client.post(
        f"/api/v1/projects/{project_id}/tasks",
        json={"title": "Viewer Accessible Task", "assignee_id": str(owner_id)},
        headers=owner_headers,
    )
    task_id = create_res.json()["data"]["id"]

    patch_res = await async_client.patch(
        f"/api/v1/tasks/{task_id}",
        json={"title": "Viewer Changed Title"},
        headers=viewer_headers,
    )

    assert patch_res.status_code == 403
    assert patch_res.json()["error"]["code"] == "FORBIDDEN"


@pytest.mark.asyncio
async def test_update_task_api_invalid_assignee(async_client: AsyncClient) -> None:
    """Integration test: OWNER updating assignee to non-workspace member -> 400 INVALID_ASSIGNEE."""
    owner_headers, owner_id = await _create_test_user(async_client, prefix="upd_inv_owner")

    workspace = await _create_workspace_with_member(owner_id=owner_id)

    proj_res = await async_client.post(
        f"/api/v1/workspaces/{workspace.id}/projects",
        json={"name": "Invalid Assignee Project"},
        headers=owner_headers,
    )
    project_id = proj_res.json()["data"]["id"]

    create_res = await async_client.post(
        f"/api/v1/projects/{project_id}/tasks",
        json={"title": "Valid Task", "assignee_id": str(owner_id)},
        headers=owner_headers,
    )
    task_id = create_res.json()["data"]["id"]

    non_member_id = uuid4()
    patch_res = await async_client.patch(
        f"/api/v1/tasks/{task_id}",
        json={"assignee_id": str(non_member_id)},
        headers=owner_headers,
    )

    assert patch_res.status_code == 400
    assert patch_res.json()["error"]["code"] == "INVALID_ASSIGNEE"


@pytest.mark.asyncio
async def test_update_task_api_archived_project(async_client: AsyncClient) -> None:
    """Integration test: OWNER updating task in ARCHIVED project -> 400 PROJECT_ARCHIVED."""
    owner_headers, owner_id = await _create_test_user(async_client, prefix="upd_arch_owner")

    workspace = await _create_workspace_with_member(owner_id=owner_id)

    proj_res = await async_client.post(
        f"/api/v1/workspaces/{workspace.id}/projects",
        json={"name": "Archived Update Project"},
        headers=owner_headers,
    )
    project_id = proj_res.json()["data"]["id"]

    create_res = await async_client.post(
        f"/api/v1/projects/{project_id}/tasks",
        json={"title": "Task Before Archive", "assignee_id": str(owner_id)},
        headers=owner_headers,
    )
    task_id = create_res.json()["data"]["id"]

    # Archive project
    archive_res = await async_client.patch(
        f"/api/v1/projects/{project_id}/archive",
        headers=owner_headers,
    )
    assert archive_res.status_code == 200

    # Attempt to update task
    patch_res = await async_client.patch(
        f"/api/v1/tasks/{task_id}",
        json={"title": "Update Archived Task"},
        headers=owner_headers,
    )

    assert patch_res.status_code == 400
    assert patch_res.json()["error"]["code"] == "PROJECT_ARCHIVED"


@pytest.mark.asyncio
async def test_update_task_api_not_found(async_client: AsyncClient) -> None:
    """Integration test: Updating non-existent task or IDOR -> 404 NOT_FOUND."""
    owner_headers, owner_id = await _create_test_user(async_client, prefix="upd_nf_owner")
    random_task_id = uuid4()

    patch_res = await async_client.patch(
        f"/api/v1/tasks/{random_task_id}",
        json={"title": "Random Task Update"},
        headers=owner_headers,
    )

    assert patch_res.status_code == 404
    assert patch_res.json()["error"]["code"] == "NOT_FOUND"


@pytest.mark.asyncio
async def test_update_task_api_validation_error(async_client: AsyncClient) -> None:
    """Integration test: Payload with empty title or >500 chars -> 422 UNPROCESSABLE_ENTITY."""
    owner_headers, owner_id = await _create_test_user(async_client, prefix="upd_val_owner")

    workspace = await _create_workspace_with_member(owner_id=owner_id)

    proj_res = await async_client.post(
        f"/api/v1/workspaces/{workspace.id}/projects",
        json={"name": "Validation Error Project"},
        headers=owner_headers,
    )
    project_id = proj_res.json()["data"]["id"]

    create_res = await async_client.post(
        f"/api/v1/projects/{project_id}/tasks",
        json={"title": "Valid Task Title", "assignee_id": str(owner_id)},
        headers=owner_headers,
    )
    task_id = create_res.json()["data"]["id"]

    # Empty title
    empty_res = await async_client.patch(
        f"/api/v1/tasks/{task_id}",
        json={"title": "   "},
        headers=owner_headers,
    )
    assert empty_res.status_code == 422

    # Title > 500 chars
    long_res = await async_client.patch(
        f"/api/v1/tasks/{task_id}",
        json={"title": "A" * 501},
        headers=owner_headers,
    )
    assert long_res.status_code == 422


# ============================================================================
# TH-005.4 Integration Tests: PATCH /tasks/{task_id}/status & priority
# ============================================================================


@pytest.mark.asyncio
async def test_patch_task_status_api_success(async_client: AsyncClient) -> None:
    """Integration test: Assignee (EDITOR) updates status via PATCH /status -> 200 OK."""
    owner_headers, owner_id = await _create_test_user(async_client, prefix="st_succ_owner")
    editor_headers, editor_id = await _create_test_user(async_client, prefix="st_succ_editor")

    workspace = await _create_workspace_with_member(
        owner_id=owner_id,
        member_id=editor_id,
        role=WorkspaceRole.EDITOR,
    )

    proj_res = await async_client.post(
        f"/api/v1/workspaces/{workspace.id}/projects",
        json={"name": "Status API Project"},
        headers=owner_headers,
    )
    project_id = proj_res.json()["data"]["id"]

    create_res = await async_client.post(
        f"/api/v1/projects/{project_id}/tasks",
        json={"title": "Status Update Task", "assignee_id": str(editor_id)},
        headers=owner_headers,
    )
    task_id = create_res.json()["data"]["id"]

    # Editor (Assignee) changes status to IN_PROGRESS
    res = await async_client.patch(
        f"/api/v1/tasks/{task_id}/status",
        json={"status": "IN_PROGRESS"},
        headers=editor_headers,
    )
    assert res.status_code == 200
    data = res.json()["data"]
    assert data["id"] == task_id
    assert data["status"] == "IN_PROGRESS"

    # Editor changes status to DONE
    res_done = await async_client.patch(
        f"/api/v1/tasks/{task_id}/status",
        json={"status": "DONE"},
        headers=editor_headers,
    )
    assert res_done.status_code == 200
    assert res_done.json()["data"]["status"] == "DONE"


@pytest.mark.asyncio
async def test_patch_task_status_api_invalid_enum(async_client: AsyncClient) -> None:
    """Integration test: Invalid status enum -> 422 UNPROCESSABLE_ENTITY."""
    owner_headers, owner_id = await _create_test_user(async_client, prefix="st_inv_owner")
    workspace = await _create_workspace_with_member(owner_id=owner_id)

    proj_res = await async_client.post(
        f"/api/v1/workspaces/{workspace.id}/projects",
        json={"name": "Invalid Status Project"},
        headers=owner_headers,
    )
    project_id = proj_res.json()["data"]["id"]

    create_res = await async_client.post(
        f"/api/v1/projects/{project_id}/tasks",
        json={"title": "Invalid Status Task", "assignee_id": str(owner_id)},
        headers=owner_headers,
    )
    task_id = create_res.json()["data"]["id"]

    res = await async_client.patch(
        f"/api/v1/tasks/{task_id}/status",
        json={"status": "INVALID_STATUS"},
        headers=owner_headers,
    )
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_patch_task_status_api_forbidden(async_client: AsyncClient) -> None:
    """Integration test: Non-assignee EDITOR or VIEWER updating status -> 403 FORBIDDEN."""
    owner_headers, owner_id = await _create_test_user(async_client, prefix="st_forb_owner")
    editor1_headers, editor1_id = await _create_test_user(async_client, prefix="st_forb_ed1")
    editor2_headers, editor2_id = await _create_test_user(async_client, prefix="st_forb_ed2")
    viewer_headers, viewer_id = await _create_test_user(async_client, prefix="st_forb_vw")

    workspace = await _create_workspace_with_member(
        owner_id=owner_id,
        member_id=editor1_id,
        role=WorkspaceRole.EDITOR,
    )

    # Add editor2 and viewer as members of workspace
    engine = create_async_engine(settings.DATABASE_URL)
    session_factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        session.add(
            WorkspaceMember(
                workspace_id=workspace.id, user_id=editor2_id, role=WorkspaceRole.EDITOR
            )
        )
        session.add(
            WorkspaceMember(workspace_id=workspace.id, user_id=viewer_id, role=WorkspaceRole.VIEWER)
        )
        await session.commit()

    await engine.dispose()

    proj_res = await async_client.post(
        f"/api/v1/workspaces/{workspace.id}/projects",
        json={"name": "Forbidden Status Project"},
        headers=owner_headers,
    )
    project_id = proj_res.json()["data"]["id"]

    # Task assigned to Editor 1
    create_res = await async_client.post(
        f"/api/v1/projects/{project_id}/tasks",
        json={"title": "Task Assigned to Ed1", "assignee_id": str(editor1_id)},
        headers=owner_headers,
    )
    task_id = create_res.json()["data"]["id"]

    # Editor 2 attempts to change status of Editor 1's task -> 403
    res_ed2 = await async_client.patch(
        f"/api/v1/tasks/{task_id}/status",
        json={"status": "IN_PROGRESS"},
        headers=editor2_headers,
    )
    assert res_ed2.status_code == 403
    assert res_ed2.json()["error"]["code"] == "FORBIDDEN"

    # Viewer attempts to change status -> 403
    res_vw = await async_client.patch(
        f"/api/v1/tasks/{task_id}/status",
        json={"status": "IN_PROGRESS"},
        headers=viewer_headers,
    )
    assert res_vw.status_code == 403
    assert res_vw.json()["error"]["code"] == "FORBIDDEN"


@pytest.mark.asyncio
async def test_patch_task_priority_api_success(async_client: AsyncClient) -> None:
    """Integration test: Priority update via PATCH /priority -> 200 OK."""
    owner_headers, owner_id = await _create_test_user(async_client, prefix="pr_succ_owner")
    workspace = await _create_workspace_with_member(owner_id=owner_id)

    proj_res = await async_client.post(
        f"/api/v1/workspaces/{workspace.id}/projects",
        json={"name": "Priority API Project"},
        headers=owner_headers,
    )
    project_id = proj_res.json()["data"]["id"]

    create_res = await async_client.post(
        f"/api/v1/projects/{project_id}/tasks",
        json={"title": "Priority Task", "assignee_id": str(owner_id)},
        headers=owner_headers,
    )
    task_id = create_res.json()["data"]["id"]

    res = await async_client.patch(
        f"/api/v1/tasks/{task_id}/priority",
        json={"priority": "URGENT"},
        headers=owner_headers,
    )
    assert res.status_code == 200
    data = res.json()["data"]
    assert data["id"] == task_id
    assert data["priority"] == "URGENT"


@pytest.mark.asyncio
async def test_patch_task_priority_api_invalid_enum(async_client: AsyncClient) -> None:
    """Integration test: Invalid priority enum -> 422 UNPROCESSABLE_ENTITY."""
    owner_headers, owner_id = await _create_test_user(async_client, prefix="pr_inv_owner")
    workspace = await _create_workspace_with_member(owner_id=owner_id)

    proj_res = await async_client.post(
        f"/api/v1/workspaces/{workspace.id}/projects",
        json={"name": "Invalid Priority Project"},
        headers=owner_headers,
    )
    project_id = proj_res.json()["data"]["id"]

    create_res = await async_client.post(
        f"/api/v1/projects/{project_id}/tasks",
        json={"title": "Invalid Priority Task", "assignee_id": str(owner_id)},
        headers=owner_headers,
    )
    task_id = create_res.json()["data"]["id"]

    res = await async_client.patch(
        f"/api/v1/tasks/{task_id}/priority",
        json={"priority": "SUPER_HIGH"},
        headers=owner_headers,
    )
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_patch_task_priority_api_forbidden(async_client: AsyncClient) -> None:
    """Integration test: Non-assignee EDITOR or VIEWER updating priority -> 403 FORBIDDEN."""
    owner_headers, owner_id = await _create_test_user(async_client, prefix="pr_forb_owner")
    editor1_headers, editor1_id = await _create_test_user(async_client, prefix="pr_forb_ed1")
    editor2_headers, editor2_id = await _create_test_user(async_client, prefix="pr_forb_ed2")
    viewer_headers, viewer_id = await _create_test_user(async_client, prefix="pr_forb_vw")

    workspace = await _create_workspace_with_member(
        owner_id=owner_id,
        member_id=editor1_id,
        role=WorkspaceRole.EDITOR,
    )

    engine = create_async_engine(settings.DATABASE_URL)
    session_factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        session.add(
            WorkspaceMember(
                workspace_id=workspace.id, user_id=editor2_id, role=WorkspaceRole.EDITOR
            )
        )
        session.add(
            WorkspaceMember(workspace_id=workspace.id, user_id=viewer_id, role=WorkspaceRole.VIEWER)
        )
        await session.commit()
    await engine.dispose()

    proj_res = await async_client.post(
        f"/api/v1/workspaces/{workspace.id}/projects",
        json={"name": "Forbidden Priority Project"},
        headers=owner_headers,
    )
    project_id = proj_res.json()["data"]["id"]

    create_res = await async_client.post(
        f"/api/v1/projects/{project_id}/tasks",
        json={"title": "Priority Task Assigned to Ed1", "assignee_id": str(editor1_id)},
        headers=owner_headers,
    )
    task_id = create_res.json()["data"]["id"]

    # Non-assignee Editor 2 attempts to change priority -> 403
    res_ed2 = await async_client.patch(
        f"/api/v1/tasks/{task_id}/priority",
        json={"priority": "URGENT"},
        headers=editor2_headers,
    )
    assert res_ed2.status_code == 403
    assert res_ed2.json()["error"]["code"] == "FORBIDDEN"

    # Viewer attempts to change priority -> 403
    res_vw = await async_client.patch(
        f"/api/v1/tasks/{task_id}/priority",
        json={"priority": "HIGH"},
        headers=viewer_headers,
    )
    assert res_vw.status_code == 403
    assert res_vw.json()["error"]["code"] == "FORBIDDEN"


@pytest.mark.asyncio
@pytest.mark.parametrize("status_val", ["TODO", "IN_PROGRESS", "IN_REVIEW", "DONE"])
async def test_patch_task_status_all_enums_api(async_client: AsyncClient, status_val: str) -> None:
    """Integration test: All valid status enums via PATCH /status -> 200 OK."""
    owner_headers, owner_id = await _create_test_user(
        async_client, prefix=f"st_enum_{status_val.lower()}"
    )
    workspace = await _create_workspace_with_member(owner_id=owner_id)

    proj_res = await async_client.post(
        f"/api/v1/workspaces/{workspace.id}/projects",
        json={"name": f"Status Enum Proj {status_val}"},
        headers=owner_headers,
    )
    project_id = proj_res.json()["data"]["id"]

    create_res = await async_client.post(
        f"/api/v1/projects/{project_id}/tasks",
        json={"title": "Status Enum Task", "assignee_id": str(owner_id)},
        headers=owner_headers,
    )
    task_id = create_res.json()["data"]["id"]

    res = await async_client.patch(
        f"/api/v1/tasks/{task_id}/status",
        json={"status": status_val},
        headers=owner_headers,
    )
    assert res.status_code == 200
    assert res.json()["data"]["status"] == status_val


@pytest.mark.asyncio
@pytest.mark.parametrize("priority_val", ["LOW", "MEDIUM", "HIGH", "URGENT"])
async def test_patch_task_priority_all_enums_api(
    async_client: AsyncClient, priority_val: str
) -> None:
    """Integration test: All valid priority enums via PATCH /priority -> 200 OK."""
    owner_headers, owner_id = await _create_test_user(
        async_client, prefix=f"pr_enum_{priority_val.lower()}"
    )
    workspace = await _create_workspace_with_member(owner_id=owner_id)

    proj_res = await async_client.post(
        f"/api/v1/workspaces/{workspace.id}/projects",
        json={"name": f"Priority Enum Proj {priority_val}"},
        headers=owner_headers,
    )
    project_id = proj_res.json()["data"]["id"]

    create_res = await async_client.post(
        f"/api/v1/projects/{project_id}/tasks",
        json={"title": "Priority Enum Task", "assignee_id": str(owner_id)},
        headers=owner_headers,
    )
    task_id = create_res.json()["data"]["id"]

    res = await async_client.patch(
        f"/api/v1/tasks/{task_id}/priority",
        json={"priority": priority_val},
        headers=owner_headers,
    )
    assert res.status_code == 200
    assert res.json()["data"]["priority"] == priority_val


# ============================================================================
# TH-005.5 Integration Tests: DELETE /tasks/{task_id}
# ============================================================================


@pytest.mark.asyncio
async def test_delete_task_api_success_owner(async_client: AsyncClient) -> None:
    """Integration test: OWNER deletes task via DELETE /tasks/{task_id} -> 204 No Content."""
    owner_headers, owner_id = await _create_test_user(async_client, prefix="del_owner")
    workspace = await _create_workspace_with_member(owner_id=owner_id)

    proj_res = await async_client.post(
        f"/api/v1/workspaces/{workspace.id}/projects",
        json={"name": "Delete Task API Project"},
        headers=owner_headers,
    )
    project_id = proj_res.json()["data"]["id"]

    create_res = await async_client.post(
        f"/api/v1/projects/{project_id}/tasks",
        json={"title": "Task to be Deleted", "assignee_id": str(owner_id)},
        headers=owner_headers,
    )
    task_id = create_res.json()["data"]["id"]

    # Delete task as OWNER
    del_res = await async_client.delete(
        f"/api/v1/tasks/{task_id}",
        headers=owner_headers,
    )
    assert del_res.status_code == 204

    # Verify task is deleted via GET detail -> 404
    get_res = await async_client.get(
        f"/api/v1/tasks/{task_id}",
        headers=owner_headers,
    )
    assert get_res.status_code == 404


@pytest.mark.asyncio
async def test_delete_task_api_success_admin(async_client: AsyncClient) -> None:
    """Integration test: System ADMIN deletes task -> 204 No Content."""
    owner_headers, owner_id = await _create_test_user(async_client, prefix="del_adm_owner")
    admin_headers, _ = await _create_test_user(async_client, prefix="del_admin")

    # Set user role to ADMIN in DB
    engine = create_async_engine(settings.DATABASE_URL)
    session_factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        from app.models.enums import UserRole
        from app.models.user import User

        # Find admin user by checking email in headers/auth
        # We can extract user_id by making GET /users/me
        me_res = await async_client.get("/api/v1/users/me", headers=admin_headers)
        admin_user_id = UUID(me_res.json()["data"]["id"])

        admin_db = await session.get(User, admin_user_id)
        if admin_db:
            admin_db.role = UserRole.ADMIN
            await session.commit()
    await engine.dispose()

    workspace = await _create_workspace_with_member(owner_id=owner_id)

    proj_res = await async_client.post(
        f"/api/v1/workspaces/{workspace.id}/projects",
        json={"name": "Admin Delete Project"},
        headers=owner_headers,
    )
    project_id = proj_res.json()["data"]["id"]

    create_res = await async_client.post(
        f"/api/v1/projects/{project_id}/tasks",
        json={"title": "Admin Deletable Task", "assignee_id": str(owner_id)},
        headers=owner_headers,
    )
    task_id = create_res.json()["data"]["id"]

    del_res = await async_client.delete(
        f"/api/v1/tasks/{task_id}",
        headers=admin_headers,
    )
    assert del_res.status_code == 204


@pytest.mark.asyncio
async def test_delete_task_api_forbidden_editor(async_client: AsyncClient) -> None:
    """Integration test: EDITOR calling DELETE /tasks/{task_id} -> 403 FORBIDDEN."""
    owner_headers, owner_id = await _create_test_user(async_client, prefix="del_ed_owner")
    editor_headers, editor_id = await _create_test_user(async_client, prefix="del_ed_editor")

    workspace = await _create_workspace_with_member(
        owner_id=owner_id,
        member_id=editor_id,
        role=WorkspaceRole.EDITOR,
    )

    proj_res = await async_client.post(
        f"/api/v1/workspaces/{workspace.id}/projects",
        json={"name": "Editor Delete Project"},
        headers=owner_headers,
    )
    project_id = proj_res.json()["data"]["id"]

    create_res = await async_client.post(
        f"/api/v1/projects/{project_id}/tasks",
        json={"title": "Editor Assigned Task", "assignee_id": str(editor_id)},
        headers=owner_headers,
    )
    task_id = create_res.json()["data"]["id"]

    del_res = await async_client.delete(
        f"/api/v1/tasks/{task_id}",
        headers=editor_headers,
    )
    assert del_res.status_code == 403
    assert del_res.json()["error"]["code"] == "FORBIDDEN"


@pytest.mark.asyncio
async def test_delete_task_api_forbidden_viewer(async_client: AsyncClient) -> None:
    """Integration test: VIEWER calling DELETE /tasks/{task_id} -> 403 FORBIDDEN."""
    owner_headers, owner_id = await _create_test_user(async_client, prefix="del_vw_owner")
    viewer_headers, viewer_id = await _create_test_user(async_client, prefix="del_vw_viewer")

    workspace = await _create_workspace_with_member(
        owner_id=owner_id,
        member_id=viewer_id,
        role=WorkspaceRole.VIEWER,
    )

    proj_res = await async_client.post(
        f"/api/v1/workspaces/{workspace.id}/projects",
        json={"name": "Viewer Delete Project"},
        headers=owner_headers,
    )
    project_id = proj_res.json()["data"]["id"]

    create_res = await async_client.post(
        f"/api/v1/projects/{project_id}/tasks",
        json={"title": "Viewer Accessible Task", "assignee_id": str(owner_id)},
        headers=owner_headers,
    )
    task_id = create_res.json()["data"]["id"]

    del_res = await async_client.delete(
        f"/api/v1/tasks/{task_id}",
        headers=viewer_headers,
    )
    assert del_res.status_code == 403
    assert del_res.json()["error"]["code"] == "FORBIDDEN"


@pytest.mark.asyncio
async def test_delete_task_api_not_found(async_client: AsyncClient) -> None:
    """Integration test: Random task_id -> 404 NOT_FOUND."""
    owner_headers, _ = await _create_test_user(async_client, prefix="del_nf_owner")
    random_task_id = uuid4()

    del_res = await async_client.delete(
        f"/api/v1/tasks/{random_task_id}",
        headers=owner_headers,
    )
    assert del_res.status_code == 404
    assert del_res.json()["error"]["code"] == "NOT_FOUND"


@pytest.mark.asyncio
async def test_delete_task_api_not_found_idor(async_client: AsyncClient) -> None:
    """Integration test: Outsider user deleting task -> 404 NOT_FOUND (IDOR Guard)."""
    owner_headers, owner_id = await _create_test_user(async_client, prefix="del_idor_owner")
    outsider_headers, _ = await _create_test_user(async_client, prefix="del_idor_out")

    workspace = await _create_workspace_with_member(owner_id=owner_id)

    proj_res = await async_client.post(
        f"/api/v1/workspaces/{workspace.id}/projects",
        json={"name": "IDOR Delete Project"},
        headers=owner_headers,
    )
    project_id = proj_res.json()["data"]["id"]

    create_res = await async_client.post(
        f"/api/v1/projects/{project_id}/tasks",
        json={"title": "Protected Task", "assignee_id": str(owner_id)},
        headers=owner_headers,
    )
    task_id = create_res.json()["data"]["id"]

    del_res = await async_client.delete(
        f"/api/v1/tasks/{task_id}",
        headers=outsider_headers,
    )
    assert del_res.status_code == 404
    assert del_res.json()["error"]["code"] == "NOT_FOUND"
