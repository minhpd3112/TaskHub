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
from app.schemas.task import TaskCreateRequest, TaskUpdateRequest
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


@pytest.mark.asyncio
async def test_list_tasks_success(task_service: TaskService) -> None:
    """Test listing tasks successfully for workspace OWNER with pagination."""
    project_id = uuid4()
    workspace_id = uuid4()
    owner_user = User(
        id=uuid4(),
        email="owner@example.com",
        full_name="Owner User",
        role=UserRole.MEMBER,
        is_active=True,
    )
    sample_project = Project(id=project_id, workspace_id=workspace_id, name="Test Project")
    owner_member = WorkspaceMember(
        workspace_id=workspace_id, user_id=owner_user.id, role=WorkspaceRole.OWNER
    )

    t1 = Task(
        id=uuid4(),
        project_id=project_id,
        created_by=owner_user.id,
        assignee_id=owner_user.id,
        title="Task 1",
        status=TaskStatus.TODO,
        priority=TaskPriority.HIGH,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
        assignee=owner_user,
        labels=[],
    )

    task_service.project_repo.get_by_id = AsyncMock(return_value=sample_project)
    task_service.workspace_repo.get_member = AsyncMock(return_value=owner_member)
    task_service.task_repo.list_tasks_by_project = AsyncMock(return_value=([t1], 1))

    res = await task_service.list_tasks(
        project_id=project_id,
        current_user=owner_user,
        page=1,
        limit=20,
    )

    assert res.pagination.total == 1
    assert res.pagination.page == 1
    assert len(res.data) == 1
    assert res.data[0].id == t1.id


@pytest.mark.asyncio
async def test_list_tasks_scoped_for_editor(task_service: TaskService) -> None:
    """Test EDITOR listing tasks passes editor_id for scoped visibility."""
    project_id = uuid4()
    workspace_id = uuid4()
    editor_user = User(
        id=uuid4(),
        email="editor@example.com",
        full_name="Editor User",
        role=UserRole.MEMBER,
        is_active=True,
    )
    sample_project = Project(id=project_id, workspace_id=workspace_id, name="Test Project")
    editor_member = WorkspaceMember(
        workspace_id=workspace_id, user_id=editor_user.id, role=WorkspaceRole.EDITOR
    )

    task_service.project_repo.get_by_id = AsyncMock(return_value=sample_project)
    task_service.workspace_repo.get_member = AsyncMock(return_value=editor_member)
    task_service.task_repo.list_tasks_by_project = AsyncMock(return_value=([], 0))

    res = await task_service.list_tasks(
        project_id=project_id,
        current_user=editor_user,
        page=1,
        limit=20,
    )

    assert res.pagination.total == 0
    task_service.task_repo.list_tasks_by_project.assert_called_once_with(
        project_id=project_id,
        status=None,
        priority=None,
        assignee_id=None,
        due_date=None,
        editor_id=editor_user.id,
        page=1,
        limit=20,
    )


@pytest.mark.asyncio
async def test_list_tasks_non_member_raises_404(task_service: TaskService) -> None:
    """Test non-workspace member listing tasks raises NotFoundError (404 IDOR Guard)."""
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

    with pytest.raises(NotFoundError) as exc_info:
        await task_service.list_tasks(
            project_id=project_id,
            current_user=outsider,
        )

    assert exc_info.value.code == "NOT_FOUND"
    assert "Project không tồn tại" in exc_info.value.message


@pytest.mark.asyncio
async def test_get_task_detail_success(task_service: TaskService) -> None:
    """Test fetching task detail successfully with relationships."""
    task_id = uuid4()
    project_id = uuid4()
    workspace_id = uuid4()
    owner_user = User(
        id=uuid4(),
        email="owner@example.com",
        full_name="Owner User",
        role=UserRole.MEMBER,
        is_active=True,
    )
    sample_project = Project(id=project_id, workspace_id=workspace_id, name="Test Project")
    owner_member = WorkspaceMember(
        workspace_id=workspace_id, user_id=owner_user.id, role=WorkspaceRole.OWNER
    )

    t_detail = Task(
        id=task_id,
        project_id=project_id,
        project=sample_project,
        created_by=owner_user.id,
        creator=owner_user,
        assignee_id=owner_user.id,
        assignee=owner_user,
        title="Detail Task",
        description="Detailed description",
        status=TaskStatus.IN_PROGRESS,
        priority=TaskPriority.HIGH,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
        labels=[],
        comments=[],
    )

    task_service.task_repo.get_task_detail = AsyncMock(return_value=t_detail)
    task_service.workspace_repo.get_member = AsyncMock(return_value=owner_member)

    res = await task_service.get_task_detail(task_id=task_id, current_user=owner_user)

    assert res.id == task_id
    assert res.title == "Detail Task"


@pytest.mark.asyncio
async def test_get_task_detail_editor_other_task_raises_404(task_service: TaskService) -> None:
    """Test EDITOR accessing task assigned to another user raises NotFoundError (404 Guard)."""
    task_id = uuid4()
    project_id = uuid4()
    workspace_id = uuid4()
    editor_user = User(
        id=uuid4(),
        email="editor@example.com",
        full_name="Editor User",
        role=UserRole.MEMBER,
        is_active=True,
    )
    other_user = User(
        id=uuid4(),
        email="other@example.com",
        full_name="Other User",
        role=UserRole.MEMBER,
        is_active=True,
    )
    sample_project = Project(id=project_id, workspace_id=workspace_id, name="Test Project")
    editor_member = WorkspaceMember(
        workspace_id=workspace_id, user_id=editor_user.id, role=WorkspaceRole.EDITOR
    )

    t_detail = Task(
        id=task_id,
        project_id=project_id,
        project=sample_project,
        created_by=other_user.id,
        creator=other_user,
        assignee_id=other_user.id,  # Assigned to other_user!
        assignee=other_user,
        title="Other's Task",
        status=TaskStatus.TODO,
        priority=TaskPriority.MEDIUM,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
        labels=[],
        comments=[],
    )

    task_service.task_repo.get_task_detail = AsyncMock(return_value=t_detail)
    task_service.workspace_repo.get_member = AsyncMock(return_value=editor_member)

    with pytest.raises(NotFoundError) as exc_info:
        await task_service.get_task_detail(task_id=task_id, current_user=editor_user)

    assert exc_info.value.code == "NOT_FOUND"
    assert "Task không tồn tại" in exc_info.value.message


@pytest.mark.asyncio
async def test_update_task_success_owner(task_service: TaskService) -> None:
    """Test updating task successfully by workspace OWNER."""
    task_id = uuid4()
    project_id = uuid4()
    workspace_id = uuid4()
    owner_user = User(
        id=uuid4(), email="owner@example.com", full_name="Owner User", role=UserRole.MEMBER
    )
    assignee_user = User(
        id=uuid4(), email="assignee@example.com", full_name="Assignee User", role=UserRole.MEMBER
    )

    sample_project = Project(
        id=project_id, workspace_id=workspace_id, name="Test Project", status=ProjectStatus.ACTIVE
    )
    owner_member = WorkspaceMember(
        workspace_id=workspace_id, user_id=owner_user.id, role=WorkspaceRole.OWNER
    )
    assignee_member = WorkspaceMember(
        workspace_id=workspace_id, user_id=assignee_user.id, role=WorkspaceRole.EDITOR
    )

    existing_task = Task(
        id=task_id,
        project_id=project_id,
        project=sample_project,
        created_by=owner_user.id,
        assignee_id=owner_user.id,
        title="Old Title",
        description="Old Description",
        status=TaskStatus.TODO,
        priority=TaskPriority.MEDIUM,
        due_date=date(2026, 1, 1),
    )
    updated_task = Task(
        id=task_id,
        project_id=project_id,
        project=sample_project,
        created_by=owner_user.id,
        assignee_id=assignee_user.id,
        title="New Title",
        description="New Description",
        status=TaskStatus.IN_PROGRESS,
        priority=TaskPriority.HIGH,
        due_date=date(2026, 2, 1),
    )

    task_service.task_repo.get_task_detail = AsyncMock(return_value=existing_task)
    task_service.workspace_repo.get_member = AsyncMock(
        side_effect=lambda ws_id, u_id: owner_member if u_id == owner_user.id else assignee_member
    )
    task_service.task_repo.update_task = AsyncMock(return_value=updated_task)
    mock_redis = AsyncMock()
    mock_redis.keys = AsyncMock(return_value=[b"tasks:project:key1"])
    task_service.redis = mock_redis

    dto = TaskUpdateRequest(
        title="New Title",
        description="New Description",
        status=TaskStatus.IN_PROGRESS,
        priority=TaskPriority.HIGH,
        due_date=date(2026, 2, 1),
        assignee_id=assignee_user.id,
    )

    result = await task_service.update_task(task_id=task_id, current_user=owner_user, data=dto)

    assert result.title == "New Title"
    assert result.priority == TaskPriority.HIGH
    mock_redis.delete.assert_called_once_with(b"tasks:project:key1")


@pytest.mark.asyncio
async def test_update_task_success_admin(task_service: TaskService) -> None:
    """Test updating task successfully by system ADMIN."""
    task_id = uuid4()
    project_id = uuid4()
    workspace_id = uuid4()
    admin_user = User(
        id=uuid4(), email="admin@example.com", full_name="System Admin", role=UserRole.ADMIN
    )

    sample_project = Project(
        id=project_id, workspace_id=workspace_id, name="Test Project", status=ProjectStatus.ACTIVE
    )
    existing_task = Task(
        id=task_id, project_id=project_id, project=sample_project, assignee_id=uuid4(), title="Task"
    )
    updated_task = Task(
        id=task_id,
        project_id=project_id,
        project=sample_project,
        assignee_id=uuid4(),
        title="Updated Task",
    )

    task_service.task_repo.get_task_detail = AsyncMock(return_value=existing_task)
    task_service.task_repo.update_task = AsyncMock(return_value=updated_task)

    dto = TaskUpdateRequest(title="Updated Task")
    result = await task_service.update_task(task_id=task_id, current_user=admin_user, data=dto)

    assert result.title == "Updated Task"


@pytest.mark.asyncio
async def test_update_task_forbidden_editor(task_service: TaskService) -> None:
    """Test updating task by EDITOR raises 403 Forbidden."""
    task_id = uuid4()
    project_id = uuid4()
    workspace_id = uuid4()
    editor_user = User(id=uuid4(), email="editor@example.com", role=UserRole.MEMBER)
    sample_project = Project(id=project_id, workspace_id=workspace_id, status=ProjectStatus.ACTIVE)
    editor_member = WorkspaceMember(
        workspace_id=workspace_id, user_id=editor_user.id, role=WorkspaceRole.EDITOR
    )

    existing_task = Task(
        id=task_id, project_id=project_id, project=sample_project, assignee_id=editor_user.id
    )

    task_service.task_repo.get_task_detail = AsyncMock(return_value=existing_task)
    task_service.workspace_repo.get_member = AsyncMock(return_value=editor_member)

    dto = TaskUpdateRequest(title="Attempted Update")
    with pytest.raises(ForbiddenError) as exc_info:
        await task_service.update_task(task_id=task_id, current_user=editor_user, data=dto)

    assert exc_info.value.code == "FORBIDDEN"


@pytest.mark.asyncio
async def test_update_task_forbidden_viewer(task_service: TaskService) -> None:
    """Test updating task by VIEWER raises 403 Forbidden."""
    task_id = uuid4()
    project_id = uuid4()
    workspace_id = uuid4()
    viewer_user = User(id=uuid4(), email="viewer@example.com", role=UserRole.MEMBER)
    sample_project = Project(id=project_id, workspace_id=workspace_id, status=ProjectStatus.ACTIVE)
    viewer_member = WorkspaceMember(
        workspace_id=workspace_id, user_id=viewer_user.id, role=WorkspaceRole.VIEWER
    )

    existing_task = Task(
        id=task_id, project_id=project_id, project=sample_project, assignee_id=uuid4()
    )

    task_service.task_repo.get_task_detail = AsyncMock(return_value=existing_task)
    task_service.workspace_repo.get_member = AsyncMock(return_value=viewer_member)

    dto = TaskUpdateRequest(title="Attempted Update")
    with pytest.raises(ForbiddenError) as exc_info:
        await task_service.update_task(task_id=task_id, current_user=viewer_user, data=dto)

    assert exc_info.value.code == "FORBIDDEN"


@pytest.mark.asyncio
async def test_update_task_invalid_assignee(task_service: TaskService) -> None:
    """Test updating task assignee to a non-workspace member raises 400 INVALID_ASSIGNEE."""
    task_id = uuid4()
    project_id = uuid4()
    workspace_id = uuid4()
    owner_user = User(id=uuid4(), email="owner@example.com", role=UserRole.MEMBER)
    non_member_id = uuid4()

    sample_project = Project(id=project_id, workspace_id=workspace_id, status=ProjectStatus.ACTIVE)
    owner_member = WorkspaceMember(
        workspace_id=workspace_id, user_id=owner_user.id, role=WorkspaceRole.OWNER
    )

    existing_task = Task(
        id=task_id, project_id=project_id, project=sample_project, assignee_id=owner_user.id
    )

    task_service.task_repo.get_task_detail = AsyncMock(return_value=existing_task)
    task_service.workspace_repo.get_member = AsyncMock(
        side_effect=lambda ws_id, u_id: owner_member if u_id == owner_user.id else None
    )

    dto = TaskUpdateRequest(assignee_id=non_member_id)
    with pytest.raises(ValidationError) as exc_info:
        await task_service.update_task(task_id=task_id, current_user=owner_user, data=dto)

    assert exc_info.value.code == "INVALID_ASSIGNEE"


@pytest.mark.asyncio
async def test_update_task_archived_project(task_service: TaskService) -> None:
    """Test updating task in an archived project raises 400 PROJECT_ARCHIVED."""
    task_id = uuid4()
    project_id = uuid4()
    workspace_id = uuid4()
    owner_user = User(id=uuid4(), email="owner@example.com", role=UserRole.MEMBER)

    archived_project = Project(
        id=project_id, workspace_id=workspace_id, status=ProjectStatus.ARCHIVED
    )
    owner_member = WorkspaceMember(
        workspace_id=workspace_id, user_id=owner_user.id, role=WorkspaceRole.OWNER
    )

    existing_task = Task(
        id=task_id, project_id=project_id, project=archived_project, assignee_id=owner_user.id
    )

    task_service.task_repo.get_task_detail = AsyncMock(return_value=existing_task)
    task_service.workspace_repo.get_member = AsyncMock(return_value=owner_member)

    dto = TaskUpdateRequest(title="New Title")
    with pytest.raises(ValidationError) as exc_info:
        await task_service.update_task(task_id=task_id, current_user=owner_user, data=dto)

    assert exc_info.value.code == "PROJECT_ARCHIVED"


@pytest.mark.asyncio
async def test_update_task_not_found_idor(task_service: TaskService) -> None:
    """Test updating non-existent task or by non-workspace member raises 404 NOT_FOUND."""
    task_id = uuid4()
    project_id = uuid4()
    workspace_id = uuid4()
    stranger_user = User(id=uuid4(), email="stranger@example.com", role=UserRole.MEMBER)

    sample_project = Project(id=project_id, workspace_id=workspace_id, status=ProjectStatus.ACTIVE)
    existing_task = Task(
        id=task_id, project_id=project_id, project=sample_project, assignee_id=uuid4()
    )

    task_service.task_repo.get_task_detail = AsyncMock(return_value=existing_task)
    task_service.workspace_repo.get_member = AsyncMock(return_value=None)  # Stranger not member!

    dto = TaskUpdateRequest(title="New Title")
    with pytest.raises(NotFoundError) as exc_info:
        await task_service.update_task(task_id=task_id, current_user=stranger_user, data=dto)

    assert exc_info.value.code == "NOT_FOUND"


# ============================================================================
# TH-005.4: update_task_status & update_task_priority Unit Tests
# ============================================================================


@pytest.mark.asyncio
async def test_update_task_status_success_by_assignee(task_service: TaskService) -> None:
    """Test assignee (EDITOR) updating task status successfully."""
    task_id = uuid4()
    project_id = uuid4()
    workspace_id = uuid4()
    assignee_user = User(id=uuid4(), email="assignee@example.com", role=UserRole.MEMBER)
    sample_project = Project(id=project_id, workspace_id=workspace_id, status=ProjectStatus.ACTIVE)
    editor_member = WorkspaceMember(
        workspace_id=workspace_id, user_id=assignee_user.id, role=WorkspaceRole.EDITOR
    )
    existing_task = Task(
        id=task_id,
        project_id=project_id,
        project=sample_project,
        assignee_id=assignee_user.id,
        status=TaskStatus.TODO,
    )
    updated_task = Task(
        id=task_id,
        project_id=project_id,
        project=sample_project,
        assignee_id=assignee_user.id,
        status=TaskStatus.IN_PROGRESS,
    )

    task_service.task_repo.get_task_detail = AsyncMock(return_value=existing_task)
    task_service.workspace_repo.get_member = AsyncMock(return_value=editor_member)
    task_service.task_repo.update_status = AsyncMock(return_value=updated_task)

    result = await task_service.update_task_status(
        task_id=task_id,
        status=TaskStatus.IN_PROGRESS,
        current_user=assignee_user,
    )

    assert result.status == TaskStatus.IN_PROGRESS
    task_service.task_repo.update_status.assert_called_once_with(task_id, TaskStatus.IN_PROGRESS)


@pytest.mark.asyncio
async def test_update_task_status_success_by_owner(task_service: TaskService) -> None:
    """Test OWNER updating status of a task assigned to someone else successfully."""
    task_id = uuid4()
    project_id = uuid4()
    workspace_id = uuid4()
    owner_user = User(id=uuid4(), email="owner@example.com", role=UserRole.MEMBER)
    other_user_id = uuid4()
    sample_project = Project(id=project_id, workspace_id=workspace_id, status=ProjectStatus.ACTIVE)
    owner_member = WorkspaceMember(
        workspace_id=workspace_id, user_id=owner_user.id, role=WorkspaceRole.OWNER
    )
    existing_task = Task(
        id=task_id,
        project_id=project_id,
        project=sample_project,
        assignee_id=other_user_id,
        status=TaskStatus.TODO,
    )
    updated_task = Task(
        id=task_id,
        project_id=project_id,
        project=sample_project,
        assignee_id=other_user_id,
        status=TaskStatus.DONE,
    )

    task_service.task_repo.get_task_detail = AsyncMock(return_value=existing_task)
    task_service.workspace_repo.get_member = AsyncMock(return_value=owner_member)
    task_service.task_repo.update_status = AsyncMock(return_value=updated_task)

    result = await task_service.update_task_status(
        task_id=task_id,
        status=TaskStatus.DONE,
        current_user=owner_user,
    )

    assert result.status == TaskStatus.DONE


@pytest.mark.asyncio
async def test_update_task_status_forbidden_by_other_editor(task_service: TaskService) -> None:
    """Test EDITOR attempting to update status of another user's task raises 403 FORBIDDEN."""
    task_id = uuid4()
    project_id = uuid4()
    workspace_id = uuid4()
    editor_user = User(id=uuid4(), email="editor@example.com", role=UserRole.MEMBER)
    other_assignee_id = uuid4()
    sample_project = Project(id=project_id, workspace_id=workspace_id, status=ProjectStatus.ACTIVE)
    editor_member = WorkspaceMember(
        workspace_id=workspace_id, user_id=editor_user.id, role=WorkspaceRole.EDITOR
    )
    existing_task = Task(
        id=task_id,
        project_id=project_id,
        project=sample_project,
        assignee_id=other_assignee_id,
        status=TaskStatus.TODO,
    )

    task_service.task_repo.get_task_detail = AsyncMock(return_value=existing_task)
    task_service.workspace_repo.get_member = AsyncMock(return_value=editor_member)

    with pytest.raises(ForbiddenError) as exc_info:
        await task_service.update_task_status(
            task_id=task_id,
            status=TaskStatus.IN_PROGRESS,
            current_user=editor_user,
        )

    assert exc_info.value.code == "FORBIDDEN"
    assert "chuyển trạng thái" in exc_info.value.message


@pytest.mark.asyncio
async def test_update_task_status_forbidden_by_viewer(task_service: TaskService) -> None:
    """Test VIEWER attempting to update task status raises 403 FORBIDDEN."""
    task_id = uuid4()
    project_id = uuid4()
    workspace_id = uuid4()
    viewer_user = User(id=uuid4(), email="viewer@example.com", role=UserRole.MEMBER)
    sample_project = Project(id=project_id, workspace_id=workspace_id, status=ProjectStatus.ACTIVE)
    viewer_member = WorkspaceMember(
        workspace_id=workspace_id, user_id=viewer_user.id, role=WorkspaceRole.VIEWER
    )
    existing_task = Task(
        id=task_id,
        project_id=project_id,
        project=sample_project,
        assignee_id=uuid4(),
        status=TaskStatus.TODO,
    )

    task_service.task_repo.get_task_detail = AsyncMock(return_value=existing_task)
    task_service.workspace_repo.get_member = AsyncMock(return_value=viewer_member)

    with pytest.raises(ForbiddenError) as exc_info:
        await task_service.update_task_status(
            task_id=task_id,
            status=TaskStatus.IN_PROGRESS,
            current_user=viewer_user,
        )

    assert exc_info.value.code == "FORBIDDEN"


@pytest.mark.asyncio
async def test_update_task_status_archived_project(task_service: TaskService) -> None:
    """Test updating task status in an archived project raises 400 PROJECT_ARCHIVED."""
    task_id = uuid4()
    project_id = uuid4()
    workspace_id = uuid4()
    assignee_user = User(id=uuid4(), email="assignee@example.com", role=UserRole.MEMBER)
    archived_project = Project(
        id=project_id, workspace_id=workspace_id, status=ProjectStatus.ARCHIVED
    )
    editor_member = WorkspaceMember(
        workspace_id=workspace_id, user_id=assignee_user.id, role=WorkspaceRole.EDITOR
    )
    existing_task = Task(
        id=task_id,
        project_id=project_id,
        project=archived_project,
        assignee_id=assignee_user.id,
        status=TaskStatus.TODO,
    )

    task_service.task_repo.get_task_detail = AsyncMock(return_value=existing_task)
    task_service.workspace_repo.get_member = AsyncMock(return_value=editor_member)

    with pytest.raises(ValidationError) as exc_info:
        await task_service.update_task_status(
            task_id=task_id,
            status=TaskStatus.DONE,
            current_user=assignee_user,
        )

    assert exc_info.value.code == "PROJECT_ARCHIVED"


@pytest.mark.asyncio
async def test_update_task_status_not_found_idor(task_service: TaskService) -> None:
    """Test updating task status by non-workspace member raises 404 NOT_FOUND."""
    task_id = uuid4()
    project_id = uuid4()
    workspace_id = uuid4()
    outsider_user = User(id=uuid4(), email="outsider@example.com", role=UserRole.MEMBER)
    sample_project = Project(id=project_id, workspace_id=workspace_id, status=ProjectStatus.ACTIVE)
    existing_task = Task(
        id=task_id,
        project_id=project_id,
        project=sample_project,
        assignee_id=uuid4(),
        status=TaskStatus.TODO,
    )

    task_service.task_repo.get_task_detail = AsyncMock(return_value=existing_task)
    task_service.workspace_repo.get_member = AsyncMock(return_value=None)  # Not a member

    with pytest.raises(NotFoundError) as exc_info:
        await task_service.update_task_status(
            task_id=task_id,
            status=TaskStatus.DONE,
            current_user=outsider_user,
        )

    assert exc_info.value.code == "NOT_FOUND"


@pytest.mark.asyncio
async def test_update_task_priority_success(task_service: TaskService) -> None:
    """Test updating task priority by an EDITOR who is the task assignee succeeds."""
    task_id = uuid4()
    project_id = uuid4()
    workspace_id = uuid4()
    editor_user = User(id=uuid4(), email="editor@example.com", role=UserRole.MEMBER)
    sample_project = Project(id=project_id, workspace_id=workspace_id, status=ProjectStatus.ACTIVE)
    editor_member = WorkspaceMember(
        workspace_id=workspace_id, user_id=editor_user.id, role=WorkspaceRole.EDITOR
    )
    existing_task = Task(
        id=task_id,
        project_id=project_id,
        project=sample_project,
        assignee_id=editor_user.id,  # EDITOR is the assignee — required by new RBAC
        priority=TaskPriority.LOW,
    )
    updated_task = Task(
        id=task_id,
        project_id=project_id,
        project=sample_project,
        assignee_id=editor_user.id,
        priority=TaskPriority.URGENT,
    )

    task_service.task_repo.get_task_detail = AsyncMock(return_value=existing_task)
    task_service.workspace_repo.get_member = AsyncMock(return_value=editor_member)
    task_service.task_repo.update_priority = AsyncMock(return_value=updated_task)

    result = await task_service.update_task_priority(
        task_id=task_id,
        priority=TaskPriority.URGENT,
        current_user=editor_user,
    )

    assert result.priority == TaskPriority.URGENT
    task_service.task_repo.update_priority.assert_called_once_with(task_id, TaskPriority.URGENT)


@pytest.mark.asyncio
async def test_update_task_priority_forbidden_by_viewer(task_service: TaskService) -> None:
    """Test VIEWER attempting to update task priority raises 403 FORBIDDEN."""
    task_id = uuid4()
    project_id = uuid4()
    workspace_id = uuid4()
    viewer_user = User(id=uuid4(), email="viewer@example.com", role=UserRole.MEMBER)
    sample_project = Project(id=project_id, workspace_id=workspace_id, status=ProjectStatus.ACTIVE)
    viewer_member = WorkspaceMember(
        workspace_id=workspace_id, user_id=viewer_user.id, role=WorkspaceRole.VIEWER
    )
    existing_task = Task(
        id=task_id,
        project_id=project_id,
        project=sample_project,
        assignee_id=uuid4(),  # Viewer is not assignee
        priority=TaskPriority.MEDIUM,
    )

    task_service.task_repo.get_task_detail = AsyncMock(return_value=existing_task)
    task_service.workspace_repo.get_member = AsyncMock(return_value=viewer_member)

    with pytest.raises(ForbiddenError) as exc_info:
        await task_service.update_task_priority(
            task_id=task_id,
            priority=TaskPriority.HIGH,
            current_user=viewer_user,
        )

    assert exc_info.value.code == "FORBIDDEN"


@pytest.mark.asyncio
async def test_update_task_priority_forbidden_by_non_assignee_editor(
    task_service: TaskService,
) -> None:
    """Test non-assignee EDITOR attempting to update task priority raises 403 FORBIDDEN."""
    task_id = uuid4()
    project_id = uuid4()
    workspace_id = uuid4()
    editor_user = User(id=uuid4(), email="editor@example.com", role=UserRole.MEMBER)
    other_assignee_id = uuid4()
    sample_project = Project(id=project_id, workspace_id=workspace_id, status=ProjectStatus.ACTIVE)
    editor_member = WorkspaceMember(
        workspace_id=workspace_id, user_id=editor_user.id, role=WorkspaceRole.EDITOR
    )
    existing_task = Task(
        id=task_id,
        project_id=project_id,
        project=sample_project,
        assignee_id=other_assignee_id,
        priority=TaskPriority.LOW,
    )

    task_service.task_repo.get_task_detail = AsyncMock(return_value=existing_task)
    task_service.workspace_repo.get_member = AsyncMock(return_value=editor_member)

    with pytest.raises(ForbiddenError) as exc_info:
        await task_service.update_task_priority(
            task_id=task_id,
            priority=TaskPriority.HIGH,
            current_user=editor_user,
        )

    assert exc_info.value.code == "FORBIDDEN"
    assert "ưu tiên công việc" in exc_info.value.message


@pytest.mark.asyncio
async def test_update_task_priority_archived_project(task_service: TaskService) -> None:
    """Test updating task priority in an archived project raises 400 PROJECT_ARCHIVED."""
    task_id = uuid4()
    project_id = uuid4()
    workspace_id = uuid4()
    assignee_user = User(id=uuid4(), email="assignee@example.com", role=UserRole.MEMBER)
    archived_project = Project(
        id=project_id, workspace_id=workspace_id, status=ProjectStatus.ARCHIVED
    )
    editor_member = WorkspaceMember(
        workspace_id=workspace_id, user_id=assignee_user.id, role=WorkspaceRole.EDITOR
    )
    existing_task = Task(
        id=task_id,
        project_id=project_id,
        project=archived_project,
        assignee_id=assignee_user.id,
        priority=TaskPriority.LOW,
    )

    task_service.task_repo.get_task_detail = AsyncMock(return_value=existing_task)
    task_service.workspace_repo.get_member = AsyncMock(return_value=editor_member)

    with pytest.raises(ValidationError) as exc_info:
        await task_service.update_task_priority(
            task_id=task_id,
            priority=TaskPriority.HIGH,
            current_user=assignee_user,
        )

    assert exc_info.value.code == "PROJECT_ARCHIVED"


@pytest.mark.asyncio
async def test_update_task_priority_not_found_idor(task_service: TaskService) -> None:
    """Test updating task priority by non-workspace member raises 404 NOT_FOUND."""
    task_id = uuid4()
    project_id = uuid4()
    workspace_id = uuid4()
    outsider_user = User(id=uuid4(), email="outsider@example.com", role=UserRole.MEMBER)
    sample_project = Project(id=project_id, workspace_id=workspace_id, status=ProjectStatus.ACTIVE)
    existing_task = Task(
        id=task_id,
        project_id=project_id,
        project=sample_project,
        assignee_id=uuid4(),
        priority=TaskPriority.LOW,
    )

    task_service.task_repo.get_task_detail = AsyncMock(return_value=existing_task)
    task_service.workspace_repo.get_member = AsyncMock(return_value=None)  # Not a member

    with pytest.raises(NotFoundError) as exc_info:
        await task_service.update_task_priority(
            task_id=task_id,
            priority=TaskPriority.URGENT,
            current_user=outsider_user,
        )

    assert exc_info.value.code == "NOT_FOUND"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "status_val",
    [TaskStatus.TODO, TaskStatus.IN_PROGRESS, TaskStatus.IN_REVIEW, TaskStatus.DONE],
)
async def test_update_task_status_all_valid_enums(
    task_service: TaskService, status_val: TaskStatus
) -> None:
    """Test all valid status transitions (TODO, IN_PROGRESS, IN_REVIEW, DONE)."""
    task_id = uuid4()
    project_id = uuid4()
    workspace_id = uuid4()
    assignee_user = User(id=uuid4(), email="assignee@example.com", role=UserRole.MEMBER)
    sample_project = Project(id=project_id, workspace_id=workspace_id, status=ProjectStatus.ACTIVE)
    editor_member = WorkspaceMember(
        workspace_id=workspace_id, user_id=assignee_user.id, role=WorkspaceRole.EDITOR
    )
    existing_task = Task(
        id=task_id,
        project_id=project_id,
        project=sample_project,
        assignee_id=assignee_user.id,
        status=TaskStatus.TODO,
    )
    updated_task = Task(
        id=task_id,
        project_id=project_id,
        project=sample_project,
        assignee_id=assignee_user.id,
        status=status_val,
    )

    task_service.task_repo.get_task_detail = AsyncMock(return_value=existing_task)
    task_service.workspace_repo.get_member = AsyncMock(return_value=editor_member)
    task_service.task_repo.update_status = AsyncMock(return_value=updated_task)

    res = await task_service.update_task_status(
        task_id=task_id,
        status=status_val,
        current_user=assignee_user,
    )
    assert res.status == status_val


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "priority_val",
    [TaskPriority.LOW, TaskPriority.MEDIUM, TaskPriority.HIGH, TaskPriority.URGENT],
)
async def test_update_task_priority_all_valid_enums(
    task_service: TaskService, priority_val: TaskPriority
) -> None:
    """Test all valid priority transitions (LOW, MEDIUM, HIGH, URGENT)."""
    task_id = uuid4()
    project_id = uuid4()
    workspace_id = uuid4()
    assignee_user = User(id=uuid4(), email="assignee@example.com", role=UserRole.MEMBER)
    sample_project = Project(id=project_id, workspace_id=workspace_id, status=ProjectStatus.ACTIVE)
    editor_member = WorkspaceMember(
        workspace_id=workspace_id, user_id=assignee_user.id, role=WorkspaceRole.EDITOR
    )
    existing_task = Task(
        id=task_id,
        project_id=project_id,
        project=sample_project,
        assignee_id=assignee_user.id,
        priority=TaskPriority.LOW,
    )
    updated_task = Task(
        id=task_id,
        project_id=project_id,
        project=sample_project,
        assignee_id=assignee_user.id,
        priority=priority_val,
    )

    task_service.task_repo.get_task_detail = AsyncMock(return_value=existing_task)
    task_service.workspace_repo.get_member = AsyncMock(return_value=editor_member)
    task_service.task_repo.update_priority = AsyncMock(return_value=updated_task)

    res = await task_service.update_task_priority(
        task_id=task_id,
        priority=priority_val,
        current_user=assignee_user,
    )
    assert res.priority == priority_val
