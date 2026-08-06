from datetime import UTC, datetime
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.core.exceptions import ForbiddenError, NotFoundError
from app.models.comment import Comment
from app.models.enums import UserRole, WorkspaceRole
from app.models.project import Project
from app.models.task import Task
from app.models.user import User
from app.models.workspace import WorkspaceMember
from app.services.comment import CommentService


@pytest.fixture
def mock_db() -> AsyncMock:
    """Mock AsyncSession for unit testing."""
    return AsyncMock()


@pytest.fixture
def comment_service(mock_db: AsyncMock) -> CommentService:
    """Instantiate CommentService with mock AsyncSession."""
    return CommentService(db=mock_db)


@pytest.mark.asyncio
async def test_create_comment_success_owner(comment_service: CommentService) -> None:
    """Test OWNER creating a comment successfully."""
    task_id = uuid4()
    workspace_id = uuid4()
    project_id = uuid4()
    user_id = uuid4()

    user = User(id=user_id, email="owner@taskhub.io", role=UserRole.MEMBER, full_name="Owner User")
    project = Project(id=project_id, workspace_id=workspace_id, name="Project Alpha")
    task = Task(id=task_id, project_id=project_id, title="Test Task")
    task.project = project
    member = WorkspaceMember(workspace_id=workspace_id, user_id=user_id, role=WorkspaceRole.OWNER)

    created_comment = Comment(
        id=uuid4(), task_id=task_id, author_id=user_id, content="Great job on this task!"
    )
    created_comment.author = user

    comment_service.task_repo.get_task_detail = AsyncMock(return_value=task)
    comment_service.workspace_repo.get_member = AsyncMock(return_value=member)
    comment_service.comment_repo.create_comment = AsyncMock(return_value=created_comment)

    result = await comment_service.create_comment(
        task_id=task_id, current_user=user, content="Great job on this task!"
    )

    assert result.id == created_comment.id
    assert result.task_id == task_id
    assert result.author_id == user_id
    assert result.content == "Great job on this task!"
    comment_service.comment_repo.create_comment.assert_called_once_with(
        task_id=task_id, author_id=user_id, content="Great job on this task!"
    )


@pytest.mark.asyncio
async def test_create_comment_success_editor(comment_service: CommentService) -> None:
    """Test EDITOR creating a comment successfully."""
    task_id = uuid4()
    workspace_id = uuid4()
    project_id = uuid4()
    user_id = uuid4()

    user = User(
        id=user_id, email="editor@taskhub.io", role=UserRole.MEMBER, full_name="Editor User"
    )
    project = Project(id=project_id, workspace_id=workspace_id, name="Project Alpha")
    task = Task(id=task_id, project_id=project_id, title="Test Task")
    task.project = project
    member = WorkspaceMember(workspace_id=workspace_id, user_id=user_id, role=WorkspaceRole.EDITOR)

    created_comment = Comment(
        id=uuid4(), task_id=task_id, author_id=user_id, content="Editor update comment"
    )
    created_comment.author = user

    comment_service.task_repo.get_task_detail = AsyncMock(return_value=task)
    comment_service.workspace_repo.get_member = AsyncMock(return_value=member)
    comment_service.comment_repo.create_comment = AsyncMock(return_value=created_comment)

    result = await comment_service.create_comment(
        task_id=task_id, current_user=user, content="Editor update comment"
    )

    assert result.id == created_comment.id
    assert result.content == "Editor update comment"


@pytest.mark.asyncio
async def test_create_comment_success_viewer(comment_service: CommentService) -> None:
    """Test VIEWER creating a comment successfully."""
    task_id = uuid4()
    workspace_id = uuid4()
    project_id = uuid4()
    user_id = uuid4()

    user = User(
        id=user_id, email="viewer@taskhub.io", role=UserRole.MEMBER, full_name="Viewer User"
    )
    project = Project(id=project_id, workspace_id=workspace_id, name="Project Alpha")
    task = Task(id=task_id, project_id=project_id, title="Test Task")
    task.project = project
    member = WorkspaceMember(workspace_id=workspace_id, user_id=user_id, role=WorkspaceRole.VIEWER)

    created_comment = Comment(
        id=uuid4(), task_id=task_id, author_id=user_id, content="Viewer feedback comment"
    )
    created_comment.author = user

    comment_service.task_repo.get_task_detail = AsyncMock(return_value=task)
    comment_service.workspace_repo.get_member = AsyncMock(return_value=member)
    comment_service.comment_repo.create_comment = AsyncMock(return_value=created_comment)

    result = await comment_service.create_comment(
        task_id=task_id, current_user=user, content="Viewer feedback comment"
    )

    assert result.id == created_comment.id
    assert result.content == "Viewer feedback comment"


@pytest.mark.asyncio
async def test_create_comment_success_admin_bypass(comment_service: CommentService) -> None:
    """Test System ADMIN creating a comment without needing workspace membership."""
    task_id = uuid4()
    workspace_id = uuid4()
    project_id = uuid4()
    admin_id = uuid4()

    admin_user = User(
        id=admin_id, email="admin@taskhub.io", role=UserRole.ADMIN, full_name="System Admin"
    )
    project = Project(id=project_id, workspace_id=workspace_id, name="Project Alpha")
    task = Task(id=task_id, project_id=project_id, title="Test Task")
    task.project = project

    created_comment = Comment(
        id=uuid4(), task_id=task_id, author_id=admin_id, content="Admin intervention comment"
    )
    created_comment.author = admin_user

    comment_service.task_repo.get_task_detail = AsyncMock(return_value=task)
    comment_service.workspace_repo.get_member = AsyncMock(return_value=None)  # Not a member
    comment_service.comment_repo.create_comment = AsyncMock(return_value=created_comment)

    result = await comment_service.create_comment(
        task_id=task_id, current_user=admin_user, content="Admin intervention comment"
    )

    assert result.id == created_comment.id
    assert result.content == "Admin intervention comment"
    comment_service.workspace_repo.get_member.assert_not_called()


@pytest.mark.asyncio
async def test_create_comment_task_not_found(comment_service: CommentService) -> None:
    """Test creating a comment when task does not exist raises NotFoundError."""
    task_id = uuid4()
    user = User(id=uuid4(), email="user@taskhub.io", role=UserRole.MEMBER, full_name="Regular User")

    comment_service.task_repo.get_task_detail = AsyncMock(return_value=None)

    with pytest.raises(NotFoundError) as exc_info:
        await comment_service.create_comment(
            task_id=task_id, current_user=user, content="Test comment"
        )

    assert exc_info.value.code == "NOT_FOUND"
    assert exc_info.value.message == "Task không tồn tại"


@pytest.mark.asyncio
async def test_create_comment_non_member_idor_guard(comment_service: CommentService) -> None:
    """Test non-member user creating a comment raises NotFoundError (404 IDOR Guard)."""
    task_id = uuid4()
    workspace_id = uuid4()
    project_id = uuid4()
    user_id = uuid4()

    user = User(
        id=user_id, email="stranger@taskhub.io", role=UserRole.MEMBER, full_name="Stranger User"
    )
    project = Project(id=project_id, workspace_id=workspace_id, name="Project Alpha")
    task = Task(id=task_id, project_id=project_id, title="Test Task")
    task.project = project

    comment_service.task_repo.get_task_detail = AsyncMock(return_value=task)
    comment_service.workspace_repo.get_member = AsyncMock(return_value=None)

    with pytest.raises(NotFoundError) as exc_info:
        await comment_service.create_comment(
            task_id=task_id, current_user=user, content="Unauthorized comment attempt"
        )

    assert exc_info.value.code == "NOT_FOUND"
    assert exc_info.value.message == "Task không tồn tại"


# === LIST COMMENTS UNIT TESTS ===


@pytest.mark.asyncio
async def test_list_comments_success(comment_service: CommentService) -> None:
    """Test listing comments successfully as workspace member."""
    task_id = uuid4()
    workspace_id = uuid4()
    project_id = uuid4()
    user_id = uuid4()

    user = User(
        id=user_id, email="member@taskhub.io", role=UserRole.MEMBER, full_name="Member User"
    )
    project = Project(id=project_id, workspace_id=workspace_id, name="Project Alpha")
    task = Task(id=task_id, project_id=project_id, title="Test Task")
    task.project = project
    member = WorkspaceMember(workspace_id=workspace_id, user_id=user_id, role=WorkspaceRole.VIEWER)

    now = datetime.now(UTC)
    c1 = Comment(
        id=uuid4(),
        task_id=task_id,
        author_id=user_id,
        content="Comment 1",
        created_at=now,
    )
    c1.author = user
    c2 = Comment(
        id=uuid4(),
        task_id=task_id,
        author_id=user_id,
        content="Comment 2",
        created_at=now,
    )
    c2.author = user

    comment_service.task_repo.get_task_detail = AsyncMock(return_value=task)
    comment_service.workspace_repo.get_member = AsyncMock(return_value=member)
    comment_service.comment_repo.list_by_task = AsyncMock(return_value=([c1, c2], 2))

    res = await comment_service.list_comments(task_id=task_id, current_user=user, page=1, limit=50)

    assert len(res.data) == 2
    assert res.pagination.page == 1
    assert res.pagination.limit == 50
    assert res.pagination.total == 2
    assert res.pagination.total_pages == 1
    assert res.data[0].content == "Comment 1"
    assert res.data[1].content == "Comment 2"


@pytest.mark.asyncio
async def test_list_comments_empty(comment_service: CommentService) -> None:
    """Test listing comments when task has no comments."""
    task_id = uuid4()
    workspace_id = uuid4()
    project_id = uuid4()
    user_id = uuid4()

    user = User(
        id=user_id, email="member@taskhub.io", role=UserRole.MEMBER, full_name="Member User"
    )
    project = Project(id=project_id, workspace_id=workspace_id, name="Project Alpha")
    task = Task(id=task_id, project_id=project_id, title="Test Task")
    task.project = project
    member = WorkspaceMember(workspace_id=workspace_id, user_id=user_id, role=WorkspaceRole.OWNER)

    comment_service.task_repo.get_task_detail = AsyncMock(return_value=task)
    comment_service.workspace_repo.get_member = AsyncMock(return_value=member)
    comment_service.comment_repo.list_by_task = AsyncMock(return_value=([], 0))

    res = await comment_service.list_comments(task_id=task_id, current_user=user, page=1, limit=50)

    assert res.data == []
    assert res.pagination.total == 0
    assert res.pagination.total_pages == 0


@pytest.mark.asyncio
async def test_list_comments_task_not_found(comment_service: CommentService) -> None:
    """Test listing comments for non-existent task raises NotFoundError."""
    task_id = uuid4()
    user = User(id=uuid4(), email="user@taskhub.io", role=UserRole.MEMBER, full_name="User")

    comment_service.task_repo.get_task_detail = AsyncMock(return_value=None)

    with pytest.raises(NotFoundError) as exc_info:
        await comment_service.list_comments(task_id=task_id, current_user=user, page=1, limit=50)

    assert exc_info.value.code == "NOT_FOUND"
    assert exc_info.value.message == "Task không tồn tại"


@pytest.mark.asyncio
async def test_list_comments_non_member_idor_guard(comment_service: CommentService) -> None:
    """Test non-member user listing comments raises NotFoundError (404 IDOR Guard)."""
    task_id = uuid4()
    workspace_id = uuid4()
    project_id = uuid4()
    user_id = uuid4()

    user = User(id=user_id, email="stranger@taskhub.io", role=UserRole.MEMBER, full_name="Stranger")
    project = Project(id=project_id, workspace_id=workspace_id, name="Project Alpha")
    task = Task(id=task_id, project_id=project_id, title="Test Task")
    task.project = project

    comment_service.task_repo.get_task_detail = AsyncMock(return_value=task)
    comment_service.workspace_repo.get_member = AsyncMock(return_value=None)

    with pytest.raises(NotFoundError) as exc_info:
        await comment_service.list_comments(task_id=task_id, current_user=user, page=1, limit=50)

    assert exc_info.value.code == "NOT_FOUND"
    assert exc_info.value.message == "Task không tồn tại"


@pytest.mark.asyncio
async def test_list_comments_admin_bypass(comment_service: CommentService) -> None:
    """Test System ADMIN listing comments without workspace membership."""
    task_id = uuid4()
    workspace_id = uuid4()
    project_id = uuid4()
    admin_id = uuid4()

    admin_user = User(id=admin_id, email="admin@taskhub.io", role=UserRole.ADMIN, full_name="Admin")
    project = Project(id=project_id, workspace_id=workspace_id, name="Project Alpha")
    task = Task(id=task_id, project_id=project_id, title="Test Task")
    task.project = project

    now = datetime.now(UTC)
    c1 = Comment(
        id=uuid4(),
        task_id=task_id,
        author_id=uuid4(),
        content="Comment 1",
        created_at=now,
    )
    c1.author = User(id=c1.author_id, email="other@taskhub.io", full_name="Other User")

    comment_service.task_repo.get_task_detail = AsyncMock(return_value=task)
    comment_service.workspace_repo.get_member = AsyncMock()
    comment_service.comment_repo.list_by_task = AsyncMock(return_value=([c1], 1))

    res = await comment_service.list_comments(
        task_id=task_id, current_user=admin_user, page=1, limit=50
    )

    assert len(res.data) == 1
    assert res.data[0].content == "Comment 1"
    comment_service.workspace_repo.get_member.assert_not_called()


# === DELETE COMMENT UNIT TESTS ===


@pytest.mark.asyncio
async def test_delete_comment_success_author(comment_service: CommentService) -> None:
    """Test author (even VIEWER) deleting their own comment successfully."""
    task_id = uuid4()
    workspace_id = uuid4()
    project_id = uuid4()
    author_id = uuid4()
    comment_id = uuid4()

    author_user = User(
        id=author_id, email="author@taskhub.io", role=UserRole.MEMBER, full_name="Author User"
    )
    project = Project(id=project_id, workspace_id=workspace_id, name="Project Alpha")
    task = Task(id=task_id, project_id=project_id, title="Test Task")
    task.project = project
    member = WorkspaceMember(
        workspace_id=workspace_id, user_id=author_id, role=WorkspaceRole.VIEWER
    )

    comment = Comment(id=comment_id, task_id=task_id, author_id=author_id, content="My comment")

    comment_service.task_repo.get_task_detail = AsyncMock(return_value=task)
    comment_service.workspace_repo.get_member = AsyncMock(return_value=member)
    comment_service.comment_repo.get_comment_by_id = AsyncMock(return_value=comment)

    await comment_service.delete_comment(
        task_id=task_id, comment_id=comment_id, current_user=author_user
    )

    comment_service.db.delete.assert_called_once_with(comment)


@pytest.mark.asyncio
async def test_delete_comment_success_owner(comment_service: CommentService) -> None:
    """Test OWNER deleting another user's comment successfully."""
    task_id = uuid4()
    workspace_id = uuid4()
    project_id = uuid4()
    owner_id = uuid4()
    author_id = uuid4()
    comment_id = uuid4()

    owner_user = User(
        id=owner_id, email="owner@taskhub.io", role=UserRole.MEMBER, full_name="Owner User"
    )
    project = Project(id=project_id, workspace_id=workspace_id, name="Project Alpha")
    task = Task(id=task_id, project_id=project_id, title="Test Task")
    task.project = project
    member = WorkspaceMember(workspace_id=workspace_id, user_id=owner_id, role=WorkspaceRole.OWNER)

    comment = Comment(id=comment_id, task_id=task_id, author_id=author_id, content="User comment")

    comment_service.task_repo.get_task_detail = AsyncMock(return_value=task)
    comment_service.workspace_repo.get_member = AsyncMock(return_value=member)
    comment_service.comment_repo.get_comment_by_id = AsyncMock(return_value=comment)

    await comment_service.delete_comment(
        task_id=task_id, comment_id=comment_id, current_user=owner_user
    )

    comment_service.db.delete.assert_called_once_with(comment)


@pytest.mark.asyncio
async def test_delete_comment_success_editor(comment_service: CommentService) -> None:
    """Test EDITOR deleting another user's comment successfully."""
    task_id = uuid4()
    workspace_id = uuid4()
    project_id = uuid4()
    editor_id = uuid4()
    author_id = uuid4()
    comment_id = uuid4()

    editor_user = User(
        id=editor_id, email="editor@taskhub.io", role=UserRole.MEMBER, full_name="Editor User"
    )
    project = Project(id=project_id, workspace_id=workspace_id, name="Project Alpha")
    task = Task(id=task_id, project_id=project_id, title="Test Task")
    task.project = project
    member = WorkspaceMember(
        workspace_id=workspace_id, user_id=editor_id, role=WorkspaceRole.EDITOR
    )

    comment = Comment(id=comment_id, task_id=task_id, author_id=author_id, content="User comment")

    comment_service.task_repo.get_task_detail = AsyncMock(return_value=task)
    comment_service.workspace_repo.get_member = AsyncMock(return_value=member)
    comment_service.comment_repo.get_comment_by_id = AsyncMock(return_value=comment)

    await comment_service.delete_comment(
        task_id=task_id, comment_id=comment_id, current_user=editor_user
    )

    comment_service.db.delete.assert_called_once_with(comment)


@pytest.mark.asyncio
async def test_delete_comment_success_admin_bypass(comment_service: CommentService) -> None:
    """Test System ADMIN deleting comment without workspace membership."""
    task_id = uuid4()
    workspace_id = uuid4()
    project_id = uuid4()
    admin_id = uuid4()
    author_id = uuid4()
    comment_id = uuid4()

    admin_user = User(
        id=admin_id, email="admin@taskhub.io", role=UserRole.ADMIN, full_name="System Admin"
    )
    project = Project(id=project_id, workspace_id=workspace_id, name="Project Alpha")
    task = Task(id=task_id, project_id=project_id, title="Test Task")
    task.project = project

    comment = Comment(id=comment_id, task_id=task_id, author_id=author_id, content="User comment")

    comment_service.task_repo.get_task_detail = AsyncMock(return_value=task)
    comment_service.workspace_repo.get_member = AsyncMock()
    comment_service.comment_repo.get_comment_by_id = AsyncMock(return_value=comment)

    await comment_service.delete_comment(
        task_id=task_id, comment_id=comment_id, current_user=admin_user
    )

    comment_service.workspace_repo.get_member.assert_not_called()
    comment_service.db.delete.assert_called_once_with(comment)


@pytest.mark.asyncio
async def test_delete_comment_forbidden_viewer(comment_service: CommentService) -> None:
    """Test VIEWER attempting to delete another user's comment raises ForbiddenError."""
    task_id = uuid4()
    workspace_id = uuid4()
    project_id = uuid4()
    viewer_id = uuid4()
    author_id = uuid4()
    comment_id = uuid4()

    viewer_user = User(
        id=viewer_id, email="viewer@taskhub.io", role=UserRole.MEMBER, full_name="Viewer User"
    )
    project = Project(id=project_id, workspace_id=workspace_id, name="Project Alpha")
    task = Task(id=task_id, project_id=project_id, title="Test Task")
    task.project = project
    member = WorkspaceMember(
        workspace_id=workspace_id, user_id=viewer_id, role=WorkspaceRole.VIEWER
    )

    comment = Comment(id=comment_id, task_id=task_id, author_id=author_id, content="Author comment")

    comment_service.task_repo.get_task_detail = AsyncMock(return_value=task)
    comment_service.workspace_repo.get_member = AsyncMock(return_value=member)
    comment_service.comment_repo.get_comment_by_id = AsyncMock(return_value=comment)

    with pytest.raises(ForbiddenError) as exc_info:
        await comment_service.delete_comment(
            task_id=task_id, comment_id=comment_id, current_user=viewer_user
        )

    assert exc_info.value.code == "FORBIDDEN"
    assert exc_info.value.message == "Bạn không có quyền xóa bình luận này."


@pytest.mark.asyncio
async def test_delete_comment_task_not_found(comment_service: CommentService) -> None:
    """Test deleting comment when task does not exist raises NotFoundError."""
    task_id = uuid4()
    comment_id = uuid4()
    user = User(id=uuid4(), email="user@taskhub.io", role=UserRole.MEMBER, full_name="User")

    comment_service.task_repo.get_task_detail = AsyncMock(return_value=None)

    with pytest.raises(NotFoundError) as exc_info:
        await comment_service.delete_comment(
            task_id=task_id, comment_id=comment_id, current_user=user
        )

    assert exc_info.value.code == "NOT_FOUND"
    assert exc_info.value.message == "Task không tồn tại"


@pytest.mark.asyncio
async def test_delete_comment_comment_not_found(comment_service: CommentService) -> None:
    """Test deleting non-existent comment raises NotFoundError."""
    task_id = uuid4()
    workspace_id = uuid4()
    project_id = uuid4()
    user_id = uuid4()
    comment_id = uuid4()

    user = User(id=user_id, email="user@taskhub.io", role=UserRole.MEMBER, full_name="User")
    project = Project(id=project_id, workspace_id=workspace_id, name="Project Alpha")
    task = Task(id=task_id, project_id=project_id, title="Test Task")
    task.project = project
    member = WorkspaceMember(workspace_id=workspace_id, user_id=user_id, role=WorkspaceRole.OWNER)

    comment_service.task_repo.get_task_detail = AsyncMock(return_value=task)
    comment_service.workspace_repo.get_member = AsyncMock(return_value=member)
    comment_service.comment_repo.get_comment_by_id = AsyncMock(return_value=None)

    with pytest.raises(NotFoundError) as exc_info:
        await comment_service.delete_comment(
            task_id=task_id, comment_id=comment_id, current_user=user
        )

    assert exc_info.value.code == "NOT_FOUND"
    assert exc_info.value.message == "Comment không tồn tại"


@pytest.mark.asyncio
async def test_delete_comment_comment_wrong_task(comment_service: CommentService) -> None:
    """Test deleting comment whose task_id does not match URL task_id raises NotFoundError."""
    task_id = uuid4()
    other_task_id = uuid4()
    workspace_id = uuid4()
    project_id = uuid4()
    user_id = uuid4()
    comment_id = uuid4()

    user = User(id=user_id, email="user@taskhub.io", role=UserRole.MEMBER, full_name="User")
    project = Project(id=project_id, workspace_id=workspace_id, name="Project Alpha")
    task = Task(id=task_id, project_id=project_id, title="Test Task")
    task.project = project
    member = WorkspaceMember(workspace_id=workspace_id, user_id=user_id, role=WorkspaceRole.OWNER)

    comment = Comment(
        id=comment_id, task_id=other_task_id, author_id=user_id, content="Wrong task comment"
    )

    comment_service.task_repo.get_task_detail = AsyncMock(return_value=task)
    comment_service.workspace_repo.get_member = AsyncMock(return_value=member)
    comment_service.comment_repo.get_comment_by_id = AsyncMock(return_value=comment)

    with pytest.raises(NotFoundError) as exc_info:
        await comment_service.delete_comment(
            task_id=task_id, comment_id=comment_id, current_user=user
        )

    assert exc_info.value.code == "NOT_FOUND"
    assert exc_info.value.message == "Comment không tồn tại"


@pytest.mark.asyncio
async def test_delete_comment_non_member_idor(comment_service: CommentService) -> None:
    """Test non-member user deleting comment raises NotFoundError (404 IDOR Guard)."""
    task_id = uuid4()
    workspace_id = uuid4()
    project_id = uuid4()
    user_id = uuid4()
    comment_id = uuid4()

    user = User(id=user_id, email="stranger@taskhub.io", role=UserRole.MEMBER, full_name="Stranger")
    project = Project(id=project_id, workspace_id=workspace_id, name="Project Alpha")
    task = Task(id=task_id, project_id=project_id, title="Test Task")
    task.project = project

    comment_service.task_repo.get_task_detail = AsyncMock(return_value=task)
    comment_service.workspace_repo.get_member = AsyncMock(return_value=None)

    with pytest.raises(NotFoundError) as exc_info:
        await comment_service.delete_comment(
            task_id=task_id, comment_id=comment_id, current_user=user
        )

    assert exc_info.value.code == "NOT_FOUND"
    assert exc_info.value.message == "Task không tồn tại"
