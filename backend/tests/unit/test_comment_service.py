from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.core.exceptions import NotFoundError
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
