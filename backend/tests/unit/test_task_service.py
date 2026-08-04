from datetime import UTC, date, datetime
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from pydantic import ValidationError as PydanticValidationError

from app.core.exceptions import ForbiddenError, NotFoundError, ValidationError
from app.models.enums import ProjectStatus, TaskPriority, TaskStatus, UserRole, WorkspaceRole
from app.models.project import Project
from app.models.task import Task
from app.models.user import User
from app.models.workspace import WorkspaceMember
from app.schemas.task import TaskCreateRequest
from app.services.task import TaskService


@pytest.fixture
def mock_db() -> AsyncMock:
    """Mock AsyncSession for unit testing."""
    return AsyncMock()


@pytest.fixture
def task_service(mock_db: AsyncMock) -> TaskService:
    """Instantiate TaskService with mock AsyncSession."""
    return TaskService(db=mock_db)


@pytest.mark.asyncio
async def test_create_task_success(task_service: TaskService) -> None:
    """Test creating a task successfully by workspace OWNER or EDITOR."""
    project_id = uuid4()
    workspace_id = uuid4()
    owner_user = User(
        id=uuid4(),
        email="owner@example.com",
        full_name="Owner User",
        role=UserRole.MEMBER,
        is_active=True,
    )
    assignee_user = User(
        id=uuid4(),
        email="assignee@example.com",
        full_name="Assignee User",
        role=UserRole.MEMBER,
        is_active=True,
    )
    sample_project = Project(
        id=project_id,
        workspace_id=workspace_id,
        name="Test Project",
    )
    owner_member = WorkspaceMember(
        workspace_id=workspace_id,
        user_id=owner_user.id,
        role=WorkspaceRole.OWNER,
    )
    assignee_member = WorkspaceMember(
        workspace_id=workspace_id,
        user_id=assignee_user.id,
        role=WorkspaceRole.EDITOR,
    )
    created_task = Task(
        id=uuid4(),
        project_id=project_id,
        created_by=owner_user.id,
        assignee_id=assignee_user.id,
        title="Setup CI/CD pipeline",
        description="Configure GitHub Actions",
        status=TaskStatus.TODO,
        priority=TaskPriority.HIGH,
        due_date=date(2026, 2, 1),
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
        assignee=assignee_user,
    )

    task_service.project_repo.get_by_id = AsyncMock(return_value=sample_project)
    task_service.workspace_repo.get_member = AsyncMock(
        side_effect=lambda ws_id, u_id: owner_member if u_id == owner_user.id else assignee_member
    )
    task_service.task_repo.create_task = AsyncMock(return_value=created_task)

    bg_tasks = MagicMock()
    dto = TaskCreateRequest(
        title="Setup CI/CD pipeline",
        description="Configure GitHub Actions",
        status=TaskStatus.TODO,
        priority=TaskPriority.HIGH,
        due_date=date(2026, 2, 1),
        assignee_id=assignee_user.id,
    )

    result = await task_service.create_task(
        project_id=project_id,
        current_user=owner_user,
        dto=dto,
        background_tasks=bg_tasks,
    )

    assert result.id == created_task.id
    assert result.title == "Setup CI/CD pipeline"
    assert result.assignee_id == assignee_user.id
    task_service.task_repo.create_task.assert_called_once_with(
        project_id=project_id,
        created_by=owner_user.id,
        assignee_id=assignee_user.id,
        title="Setup CI/CD pipeline",
        description="Configure GitHub Actions",
        status=TaskStatus.TODO,
        priority=TaskPriority.HIGH,
        due_date=date(2026, 2, 1),
    )
    bg_tasks.add_task.assert_called_once()


@pytest.mark.asyncio
async def test_create_task_forbidden_for_viewer(task_service: TaskService) -> None:
    """Test VIEWER attempting to create task raises ForbiddenError (403)."""
    project_id = uuid4()
    workspace_id = uuid4()
    viewer_user = User(
        id=uuid4(),
        email="viewer@example.com",
        full_name="Viewer User",
        role=UserRole.MEMBER,
        is_active=True,
    )
    sample_project = Project(id=project_id, workspace_id=workspace_id, name="Test Project")
    viewer_member = WorkspaceMember(
        workspace_id=workspace_id, user_id=viewer_user.id, role=WorkspaceRole.VIEWER
    )

    task_service.project_repo.get_by_id = AsyncMock(return_value=sample_project)
    task_service.workspace_repo.get_member = AsyncMock(return_value=viewer_member)

    dto = TaskCreateRequest(title="Valid Title", assignee_id=uuid4())

    with pytest.raises(ForbiddenError) as exc_info:
        await task_service.create_task(
            project_id=project_id,
            current_user=viewer_user,
            dto=dto,
        )

    assert exc_info.value.code == "FORBIDDEN"
    assert "quyền" in exc_info.value.message.lower()


@pytest.mark.asyncio
async def test_create_task_non_member_raises_404(task_service: TaskService) -> None:
    """Test user not in workspace attempting to create task raises NotFoundError (404 Guard)."""
    project_id = uuid4()
    workspace_id = uuid4()
    outsider = User(
        id=uuid4(),
        email="outsider@example.com",
        full_name="Outsider User",
        role=UserRole.MEMBER,
        is_active=True,
    )
    sample_project = Project(id=project_id, workspace_id=workspace_id, name="Test Project")

    task_service.project_repo.get_by_id = AsyncMock(return_value=sample_project)
    task_service.workspace_repo.get_member = AsyncMock(return_value=None)

    dto = TaskCreateRequest(title="Valid Title", assignee_id=uuid4())

    with pytest.raises(NotFoundError) as exc_info:
        await task_service.create_task(
            project_id=project_id,
            current_user=outsider,
            dto=dto,
        )

    assert exc_info.value.code == "NOT_FOUND"


@pytest.mark.asyncio
async def test_create_task_invalid_assignee_not_in_workspace(task_service: TaskService) -> None:
    """Test assignee_id not belonging to workspace raises ValidationError (INVALID_ASSIGNEE)."""
    project_id = uuid4()
    workspace_id = uuid4()
    editor_user = User(
        id=uuid4(),
        email="editor@example.com",
        full_name="Editor User",
        role=UserRole.MEMBER,
        is_active=True,
    )
    invalid_assignee_id = uuid4()
    sample_project = Project(id=project_id, workspace_id=workspace_id, name="Test Project")
    editor_member = WorkspaceMember(
        workspace_id=workspace_id, user_id=editor_user.id, role=WorkspaceRole.EDITOR
    )

    task_service.project_repo.get_by_id = AsyncMock(return_value=sample_project)
    task_service.workspace_repo.get_member = AsyncMock(
        side_effect=lambda ws_id, u_id: editor_member if u_id == editor_user.id else None
    )

    dto = TaskCreateRequest(title="Valid Title", assignee_id=invalid_assignee_id)

    with pytest.raises(ValidationError) as exc_info:
        await task_service.create_task(
            project_id=project_id,
            current_user=editor_user,
            dto=dto,
        )

    assert exc_info.value.code == "INVALID_ASSIGNEE"
    assert "Assignee phải là thành viên" in exc_info.value.message


@pytest.mark.asyncio
async def test_create_task_title_validation() -> None:
    """Test title validation raises PydanticValidationError for empty/whitespace title."""
    with pytest.raises(PydanticValidationError):
        TaskCreateRequest(title="   ", assignee_id=uuid4())


@pytest.mark.asyncio
async def test_create_task_archived_project_raises_validation_error(
    task_service: TaskService,
) -> None:
    """Test creating task in an ARCHIVED project raises ValidationError (PROJECT_ARCHIVED)."""
    project_id = uuid4()
    workspace_id = uuid4()
    owner_user = User(
        id=uuid4(),
        email="owner@example.com",
        full_name="Owner User",
        role=UserRole.MEMBER,
        is_active=True,
    )
    archived_project = Project(
        id=project_id,
        workspace_id=workspace_id,
        name="Archived Project",
        status=ProjectStatus.ARCHIVED,
    )

    task_service.project_repo.get_by_id = AsyncMock(return_value=archived_project)

    dto = TaskCreateRequest(title="Task in Archived Project", assignee_id=uuid4())

    with pytest.raises(ValidationError) as exc_info:
        await task_service.create_task(
            project_id=project_id,
            current_user=owner_user,
            dto=dto,
        )

    assert exc_info.value.code == "PROJECT_ARCHIVED"
    assert "ARCHIVED" in exc_info.value.message
