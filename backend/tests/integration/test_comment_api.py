from uuid import UUID, uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings
from app.models.enums import WorkspaceRole
from app.models.project import Project
from app.models.task import Task
from app.models.workspace import Workspace, WorkspaceMember


async def _create_test_user(
    async_client: AsyncClient, prefix: str = "user"
) -> tuple[dict[str, str], UUID]:
    """Helper to register and login a new user, returning auth headers and user_id."""
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


async def _create_task_in_db(
    project_id: UUID, assignee_id: UUID, created_by: UUID, title: str = "Test Task"
) -> Task:
    """Helper to create a task directly in the database."""
    engine = create_async_engine(settings.DATABASE_URL)
    session_factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        task = Task(
            project_id=project_id,
            assignee_id=assignee_id,
            created_by=created_by,
            title=title,
        )
        session.add(task)
        await session.commit()
        task_id = task.id
    await engine.dispose()
    return Task(
        id=task_id,
        project_id=project_id,
        assignee_id=assignee_id,
        created_by=created_by,
        title=title,
    )


# === TH-007.1 INTEGRATION TESTS ===


@pytest.mark.asyncio
async def test_add_comment_viewer_success(async_client: AsyncClient) -> None:
    """VIEWER adds comment to a task successfully -> 201 Created and correct response shape."""
    _owner_headers, owner_id = await _create_test_user(async_client, prefix="owner")
    viewer_headers, viewer_id = await _create_test_user(async_client, prefix="viewer")
    workspace = await _create_workspace_with_member(
        owner_id=owner_id, member_id=viewer_id, role=WorkspaceRole.VIEWER
    )
    project = await _create_project_in_db(workspace_id=workspace.id)
    task = await _create_task_in_db(
        project_id=project.id, assignee_id=owner_id, created_by=owner_id
    )

    payload = {"content": "This is a comment from VIEWER user."}
    res = await async_client.post(
        f"/api/v1/tasks/{task.id}/comments",
        headers=viewer_headers,
        json=payload,
    )

    assert res.status_code == 201
    res_data = res.json()["data"]
    assert res_data["task_id"] == str(task.id)
    assert res_data["author_id"] == str(viewer_id)
    assert res_data["content"] == "This is a comment from VIEWER user."
    assert "id" in res_data
    assert "created_at" in res_data
    assert res_data["author"]["id"] == str(viewer_id)
    assert res_data["author"]["full_name"] == "Test viewer"


@pytest.mark.asyncio
async def test_add_comment_owner_and_editor_success(async_client: AsyncClient) -> None:
    """OWNER and EDITOR add comments to task successfully -> 201 Created."""
    owner_headers, owner_id = await _create_test_user(async_client, prefix="owner")
    editor_headers, editor_id = await _create_test_user(async_client, prefix="editor")
    workspace = await _create_workspace_with_member(
        owner_id=owner_id, member_id=editor_id, role=WorkspaceRole.EDITOR
    )
    project = await _create_project_in_db(workspace_id=workspace.id)
    task = await _create_task_in_db(
        project_id=project.id, assignee_id=editor_id, created_by=owner_id
    )

    # OWNER comment
    res_owner = await async_client.post(
        f"/api/v1/tasks/{task.id}/comments",
        headers=owner_headers,
        json={"content": "Owner comment on task"},
    )
    assert res_owner.status_code == 201
    assert res_owner.json()["data"]["author_id"] == str(owner_id)

    # EDITOR comment
    res_editor = await async_client.post(
        f"/api/v1/tasks/{task.id}/comments",
        headers=editor_headers,
        json={"content": "Editor comment on task"},
    )
    assert res_editor.status_code == 201
    assert res_editor.json()["data"]["author_id"] == str(editor_id)


@pytest.mark.asyncio
async def test_add_comment_unauthorized(async_client: AsyncClient) -> None:
    """Request without authentication header -> 401 Unauthorized."""
    task_id = uuid4()
    res = await async_client.post(
        f"/api/v1/tasks/{task_id}/comments",
        json={"content": "Unauthorized comment"},
    )
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_add_comment_empty_or_whitespace_content(async_client: AsyncClient) -> None:
    """Empty or whitespace-only content -> 422 Unprocessable Entity."""
    headers, owner_id = await _create_test_user(async_client, prefix="owner")
    workspace = await _create_workspace_with_member(owner_id=owner_id)
    project = await _create_project_in_db(workspace_id=workspace.id)
    task = await _create_task_in_db(
        project_id=project.id, assignee_id=owner_id, created_by=owner_id
    )

    # Empty content
    res_empty = await async_client.post(
        f"/api/v1/tasks/{task.id}/comments",
        headers=headers,
        json={"content": ""},
    )
    assert res_empty.status_code == 422

    # Whitespace content
    res_ws = await async_client.post(
        f"/api/v1/tasks/{task.id}/comments",
        headers=headers,
        json={"content": "   \n\t  "},
    )
    assert res_ws.status_code == 422


@pytest.mark.asyncio
async def test_add_comment_content_exceeds_max_length(async_client: AsyncClient) -> None:
    """Content exceeding 5000 characters -> 422 Unprocessable Entity."""
    headers, owner_id = await _create_test_user(async_client, prefix="owner")
    workspace = await _create_workspace_with_member(owner_id=owner_id)
    project = await _create_project_in_db(workspace_id=workspace.id)
    task = await _create_task_in_db(
        project_id=project.id, assignee_id=owner_id, created_by=owner_id
    )

    long_content = "a" * 5001
    res = await async_client.post(
        f"/api/v1/tasks/{task.id}/comments",
        headers=headers,
        json={"content": long_content},
    )
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_add_comment_non_member_returns_404(async_client: AsyncClient) -> None:
    """Non-workspace member user adding comment -> 404 NOT_FOUND (IDOR Guard)."""
    _owner_headers, owner_id = await _create_test_user(async_client, prefix="owner")
    stranger_headers, _stranger_id = await _create_test_user(async_client, prefix="stranger")
    workspace = await _create_workspace_with_member(owner_id=owner_id)
    project = await _create_project_in_db(workspace_id=workspace.id)
    task = await _create_task_in_db(
        project_id=project.id, assignee_id=owner_id, created_by=owner_id
    )

    res = await async_client.post(
        f"/api/v1/tasks/{task.id}/comments",
        headers=stranger_headers,
        json={"content": "Stranger trying to comment"},
    )
    assert res.status_code == 404
    assert res.json()["error"]["code"] == "NOT_FOUND"


@pytest.mark.asyncio
async def test_add_comment_task_not_found_returns_404(async_client: AsyncClient) -> None:
    """Non-existent task_id -> 404 NOT_FOUND."""
    headers, owner_id = await _create_test_user(async_client, prefix="owner")
    await _create_workspace_with_member(owner_id=owner_id)
    random_task_id = uuid4()

    res = await async_client.post(
        f"/api/v1/tasks/{random_task_id}/comments",
        headers=headers,
        json={"content": "Commenting on missing task"},
    )
    assert res.status_code == 404
    assert res.json()["error"]["code"] == "NOT_FOUND"


@pytest.mark.asyncio
async def test_add_comment_admin_bypass_success(async_client: AsyncClient) -> None:
    """System ADMIN adding comment on task in workspace without membership -> 201."""
    _owner_headers, owner_id = await _create_test_user(async_client, prefix="owner")
    workspace = await _create_workspace_with_member(owner_id=owner_id)
    project = await _create_project_in_db(workspace_id=workspace.id)
    task = await _create_task_in_db(
        project_id=project.id, assignee_id=owner_id, created_by=owner_id
    )

    # Login as seeded system ADMIN (admin@taskhub.io / Password123!)
    login_res = await async_client.post(
        "/api/v1/auth/login",
        json={"email": "admin@taskhub.io", "password": "Password123!"},
    )
    admin_token = login_res.json()["data"]["access_token"]
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    res = await async_client.post(
        f"/api/v1/tasks/{task.id}/comments",
        headers=admin_headers,
        json={"content": "System ADMIN intervention comment"},
    )
    assert res.status_code == 201
    assert res.json()["data"]["content"] == "System ADMIN intervention comment"


# === TH-007.2 INTEGRATION TESTS ===


@pytest.mark.asyncio
async def test_list_comments_empty_success(async_client: AsyncClient) -> None:
    """Task with no comments -> 200 OK with empty data array and total == 0."""
    headers, owner_id = await _create_test_user(async_client, prefix="owner")
    workspace = await _create_workspace_with_member(owner_id=owner_id)
    project = await _create_project_in_db(workspace_id=workspace.id)
    task = await _create_task_in_db(
        project_id=project.id, assignee_id=owner_id, created_by=owner_id
    )

    res = await async_client.get(
        f"/api/v1/tasks/{task.id}/comments",
        headers=headers,
    )

    assert res.status_code == 200
    res_body = res.json()
    assert res_body["data"] == []
    assert res_body["pagination"]["page"] == 1
    assert res_body["pagination"]["limit"] == 50
    assert res_body["pagination"]["total"] == 0
    assert res_body["pagination"]["total_pages"] == 0


@pytest.mark.asyncio
async def test_list_comments_multiple_asc_order(async_client: AsyncClient) -> None:
    """Multiple comments created -> returned in ascending order by created_at."""
    owner_headers, owner_id = await _create_test_user(async_client, prefix="owner")
    viewer_headers, viewer_id = await _create_test_user(async_client, prefix="viewer")
    workspace = await _create_workspace_with_member(
        owner_id=owner_id, member_id=viewer_id, role=WorkspaceRole.VIEWER
    )
    project = await _create_project_in_db(workspace_id=workspace.id)
    task = await _create_task_in_db(
        project_id=project.id, assignee_id=owner_id, created_by=owner_id
    )

    # Create 3 comments in sequence
    res1 = await async_client.post(
        f"/api/v1/tasks/{task.id}/comments",
        headers=owner_headers,
        json={"content": "First comment by owner"},
    )
    assert res1.status_code == 201

    res2 = await async_client.post(
        f"/api/v1/tasks/{task.id}/comments",
        headers=viewer_headers,
        json={"content": "Second comment by viewer"},
    )
    assert res2.status_code == 201

    res3 = await async_client.post(
        f"/api/v1/tasks/{task.id}/comments",
        headers=owner_headers,
        json={"content": "Third comment by owner"},
    )
    assert res3.status_code == 201

    # GET list of comments as viewer
    res_list = await async_client.get(
        f"/api/v1/tasks/{task.id}/comments",
        headers=viewer_headers,
    )
    assert res_list.status_code == 200
    res_body = res_list.json()

    assert res_body["pagination"]["total"] == 3
    data = res_body["data"]
    assert len(data) == 3
    assert data[0]["content"] == "First comment by owner"
    assert data[0]["author"]["id"] == str(owner_id)
    assert data[0]["author"]["full_name"] == "Test owner"

    assert data[1]["content"] == "Second comment by viewer"
    assert data[1]["author"]["id"] == str(viewer_id)
    assert data[1]["author"]["full_name"] == "Test viewer"

    assert data[2]["content"] == "Third comment by owner"

    # Verify ascending timestamps order
    assert data[0]["created_at"] <= data[1]["created_at"] <= data[2]["created_at"]


@pytest.mark.asyncio
async def test_list_comments_pagination(async_client: AsyncClient) -> None:
    """Pagination query params limit and page correctly page through results."""
    headers, owner_id = await _create_test_user(async_client, prefix="owner")
    workspace = await _create_workspace_with_member(owner_id=owner_id)
    project = await _create_project_in_db(workspace_id=workspace.id)
    task = await _create_task_in_db(
        project_id=project.id, assignee_id=owner_id, created_by=owner_id
    )

    for i in range(1, 4):
        await async_client.post(
            f"/api/v1/tasks/{task.id}/comments",
            headers=headers,
            json={"content": f"Comment {i}"},
        )

    # Page 1, limit 2
    res_p1 = await async_client.get(
        f"/api/v1/tasks/{task.id}/comments?page=1&limit=2",
        headers=headers,
    )
    assert res_p1.status_code == 200
    p1_body = res_p1.json()
    assert len(p1_body["data"]) == 2
    assert p1_body["pagination"]["total"] == 3
    assert p1_body["pagination"]["total_pages"] == 2
    assert p1_body["data"][0]["content"] == "Comment 1"
    assert p1_body["data"][1]["content"] == "Comment 2"

    # Page 2, limit 2
    res_p2 = await async_client.get(
        f"/api/v1/tasks/{task.id}/comments?page=2&limit=2",
        headers=headers,
    )
    assert res_p2.status_code == 200
    p2_body = res_p2.json()
    assert len(p2_body["data"]) == 1
    assert p2_body["data"][0]["content"] == "Comment 3"


@pytest.mark.asyncio
async def test_list_comments_non_member_returns_404(async_client: AsyncClient) -> None:
    """Non-workspace member trying to view comments -> 404 NOT_FOUND (IDOR Guard)."""
    _owner_headers, owner_id = await _create_test_user(async_client, prefix="owner")
    stranger_headers, _stranger_id = await _create_test_user(async_client, prefix="stranger")
    workspace = await _create_workspace_with_member(owner_id=owner_id)
    project = await _create_project_in_db(workspace_id=workspace.id)
    task = await _create_task_in_db(
        project_id=project.id, assignee_id=owner_id, created_by=owner_id
    )

    res = await async_client.get(
        f"/api/v1/tasks/{task.id}/comments",
        headers=stranger_headers,
    )
    assert res.status_code == 404
    assert res.json()["error"]["code"] == "NOT_FOUND"


@pytest.mark.asyncio
async def test_list_comments_task_not_found_returns_404(async_client: AsyncClient) -> None:
    """Non-existent task_id -> 404 NOT_FOUND."""
    headers, owner_id = await _create_test_user(async_client, prefix="owner")
    await _create_workspace_with_member(owner_id=owner_id)
    random_task_id = uuid4()

    res = await async_client.get(
        f"/api/v1/tasks/{random_task_id}/comments",
        headers=headers,
    )
    assert res.status_code == 404
    assert res.json()["error"]["code"] == "NOT_FOUND"


@pytest.mark.asyncio
async def test_list_comments_unauthorized(async_client: AsyncClient) -> None:
    """Request without token -> 401 Unauthorized."""
    task_id = uuid4()
    res = await async_client.get(f"/api/v1/tasks/{task_id}/comments")
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_list_comments_admin_bypass_success(async_client: AsyncClient) -> None:
    """System ADMIN listing comments on task in workspace without membership -> 200."""
    owner_headers, owner_id = await _create_test_user(async_client, prefix="owner")
    workspace = await _create_workspace_with_member(owner_id=owner_id)
    project = await _create_project_in_db(workspace_id=workspace.id)
    task = await _create_task_in_db(
        project_id=project.id, assignee_id=owner_id, created_by=owner_id
    )

    await async_client.post(
        f"/api/v1/tasks/{task.id}/comments",
        headers=owner_headers,
        json={"content": "Owner comment for admin to view"},
    )

    # Login as seeded system ADMIN
    login_res = await async_client.post(
        "/api/v1/auth/login",
        json={"email": "admin@taskhub.io", "password": "Password123!"},
    )
    admin_token = login_res.json()["data"]["access_token"]
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    res = await async_client.get(
        f"/api/v1/tasks/{task.id}/comments",
        headers=admin_headers,
    )
    assert res.status_code == 200
    assert res.json()["pagination"]["total"] == 1
    assert res.json()["data"][0]["content"] == "Owner comment for admin to view"
