from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.core.exceptions import ConflictError, ForbiddenError, NotFoundError, ValidationError
from app.models.enums import WorkspaceRole
from app.models.label import Label, TaskLabel
from app.models.project import Project
from app.models.task import Task
from app.models.workspace import WorkspaceMember
from app.schemas.label import LabelCreateRequest
from app.services.label import LabelService


@pytest.fixture
def mock_db() -> AsyncMock:
    """Mock AsyncSession for unit testing."""
    return AsyncMock()


@pytest.fixture
def label_service(mock_db: AsyncMock) -> LabelService:
    """Instantiate LabelService with mock AsyncSession."""
    return LabelService(db=mock_db)


@pytest.mark.asyncio
async def test_create_label_success_owner(label_service: LabelService) -> None:
    """Test OWNER creates a label successfully."""
    project_id = uuid4()
    user_id = uuid4()
    workspace_id = uuid4()

    sample_project = Project(id=project_id, workspace_id=workspace_id, name="Project Alpha")
    sample_member = WorkspaceMember(
        workspace_id=workspace_id, user_id=user_id, role=WorkspaceRole.OWNER
    )
    created_label = Label(id=uuid4(), project_id=project_id, name="Bug", color="#EF4444")

    label_service.project_repo.get_by_id = AsyncMock(return_value=sample_project)
    label_service.workspace_repo.get_member = AsyncMock(return_value=sample_member)
    label_service.label_repo.get_by_project_and_name = AsyncMock(return_value=None)
    label_service.label_repo.create_label = AsyncMock(return_value=created_label)

    dto = LabelCreateRequest(name="Bug", color="#EF4444")
    result = await label_service.create_label(project_id, dto, user_id, is_admin=False)

    assert result.id == created_label.id
    assert result.name == "Bug"
    assert result.color == "#EF4444"
    label_service.label_repo.create_label.assert_called_once_with(
        project_id=project_id, name="Bug", color="#EF4444"
    )


@pytest.mark.asyncio
async def test_create_label_forbidden_editor(label_service: LabelService) -> None:
    """Test EDITOR creating label raises ForbiddenError (403) per ADR-006."""
    project_id = uuid4()
    user_id = uuid4()
    workspace_id = uuid4()

    sample_project = Project(id=project_id, workspace_id=workspace_id, name="Project Alpha")
    sample_member = WorkspaceMember(
        workspace_id=workspace_id, user_id=user_id, role=WorkspaceRole.EDITOR
    )

    label_service.project_repo.get_by_id = AsyncMock(return_value=sample_project)
    label_service.workspace_repo.get_member = AsyncMock(return_value=sample_member)

    dto = LabelCreateRequest(name="Feature", color="#3B82F6")
    with pytest.raises(ForbiddenError) as exc_info:
        await label_service.create_label(project_id, dto, user_id, is_admin=False)

    assert exc_info.value.code == "FORBIDDEN"


@pytest.mark.asyncio
async def test_create_label_forbidden_viewer(label_service: LabelService) -> None:
    """Test VIEWER creating label raises ForbiddenError (403)."""
    project_id = uuid4()
    user_id = uuid4()
    workspace_id = uuid4()

    sample_project = Project(id=project_id, workspace_id=workspace_id, name="Project Alpha")
    sample_member = WorkspaceMember(
        workspace_id=workspace_id, user_id=user_id, role=WorkspaceRole.VIEWER
    )

    label_service.project_repo.get_by_id = AsyncMock(return_value=sample_project)
    label_service.workspace_repo.get_member = AsyncMock(return_value=sample_member)

    dto = LabelCreateRequest(name="Bug", color="#EF4444")
    with pytest.raises(ForbiddenError) as exc_info:
        await label_service.create_label(project_id, dto, user_id, is_admin=False)

    assert exc_info.value.code == "FORBIDDEN"


@pytest.mark.asyncio
async def test_create_label_conflict_duplicate_name(label_service: LabelService) -> None:
    """Test creating a label with duplicate name in same project raises ConflictError (409)."""
    project_id = uuid4()
    user_id = uuid4()
    workspace_id = uuid4()

    sample_project = Project(id=project_id, workspace_id=workspace_id, name="Project Alpha")
    sample_member = WorkspaceMember(
        workspace_id=workspace_id, user_id=user_id, role=WorkspaceRole.OWNER
    )
    existing_label = Label(id=uuid4(), project_id=project_id, name="Bug", color="#EF4444")

    label_service.project_repo.get_by_id = AsyncMock(return_value=sample_project)
    label_service.workspace_repo.get_member = AsyncMock(return_value=sample_member)
    label_service.label_repo.get_by_project_and_name = AsyncMock(return_value=existing_label)

    dto = LabelCreateRequest(name="Bug", color="#EF4444")
    with pytest.raises(ConflictError) as exc_info:
        await label_service.create_label(project_id, dto, user_id, is_admin=False)

    assert exc_info.value.code == "CONFLICT"


@pytest.mark.asyncio
async def test_create_label_non_member_idor(label_service: LabelService) -> None:
    """Test non-member creating label raises NotFoundError (404 IDOR Guard)."""
    project_id = uuid4()
    user_id = uuid4()

    sample_project = Project(id=project_id, workspace_id=uuid4(), name="Project Alpha")

    label_service.project_repo.get_by_id = AsyncMock(return_value=sample_project)
    label_service.workspace_repo.get_member = AsyncMock(return_value=None)

    dto = LabelCreateRequest(name="Bug", color="#EF4444")
    with pytest.raises(NotFoundError) as exc_info:
        await label_service.create_label(project_id, dto, user_id, is_admin=False)

    assert exc_info.value.code == "NOT_FOUND"


@pytest.mark.asyncio
async def test_list_labels_success_all_roles(label_service: LabelService) -> None:
    """Test any member (including VIEWER) listing labels successfully."""
    project_id = uuid4()
    user_id = uuid4()
    workspace_id = uuid4()

    sample_project = Project(id=project_id, workspace_id=workspace_id, name="Project Alpha")
    sample_member = WorkspaceMember(
        workspace_id=workspace_id, user_id=user_id, role=WorkspaceRole.VIEWER
    )
    labels = [
        Label(id=uuid4(), project_id=project_id, name="Bug", color="#EF4444"),
        Label(id=uuid4(), project_id=project_id, name="Feature", color="#3B82F6"),
    ]

    label_service.project_repo.get_by_id = AsyncMock(return_value=sample_project)
    label_service.workspace_repo.get_member = AsyncMock(return_value=sample_member)
    label_service.label_repo.list_by_project = AsyncMock(return_value=labels)

    result = await label_service.list_labels(project_id, user_id, is_admin=False)

    assert len(result) == 2
    assert result[0].name == "Bug"
    assert result[1].name == "Feature"


@pytest.mark.asyncio
async def test_list_labels_non_member_idor(label_service: LabelService) -> None:
    """Test non-member listing labels raises NotFoundError (404 IDOR Guard)."""
    project_id = uuid4()
    user_id = uuid4()

    sample_project = Project(id=project_id, workspace_id=uuid4(), name="Project Alpha")

    label_service.project_repo.get_by_id = AsyncMock(return_value=sample_project)
    label_service.workspace_repo.get_member = AsyncMock(return_value=None)

    with pytest.raises(NotFoundError) as exc_info:
        await label_service.list_labels(project_id, user_id, is_admin=False)

    assert exc_info.value.code == "NOT_FOUND"


# === TH-006.2 UNIT TESTS ===


@pytest.mark.asyncio
async def test_assign_label_success(label_service: LabelService) -> None:
    """Test assigning a label to a task successfully by OWNER."""
    task_id = uuid4()
    label_id = uuid4()
    project_id = uuid4()
    workspace_id = uuid4()
    user_id = uuid4()

    sample_project = Project(id=project_id, workspace_id=workspace_id, name="Project Alpha")
    sample_task = Task(id=task_id, project_id=project_id, title="Test Task")
    sample_task.project = sample_project
    sample_member = WorkspaceMember(
        workspace_id=workspace_id, user_id=user_id, role=WorkspaceRole.OWNER
    )
    sample_label = Label(id=label_id, project_id=project_id, name="Bug", color="#EF4444")
    created_task_label = TaskLabel(task_id=task_id, label_id=label_id)

    label_service.task_repo.get_task_detail = AsyncMock(return_value=sample_task)
    label_service.workspace_repo.get_member = AsyncMock(return_value=sample_member)
    label_service.label_repo.get_by_id = AsyncMock(return_value=sample_label)
    label_service.label_repo.get_task_label = AsyncMock(return_value=None)
    label_service.label_repo.assign_label_to_task = AsyncMock(return_value=created_task_label)

    task_label, label = await label_service.assign_label(task_id, label_id, user_id, is_admin=False)

    assert task_label.task_id == task_id
    assert task_label.label_id == label_id
    assert label.name == "Bug"
    label_service.label_repo.assign_label_to_task.assert_called_once_with(task_id, label_id)


@pytest.mark.asyncio
async def test_assign_label_idempotent(label_service: LabelService) -> None:
    """Test assigning an already assigned label returns existing task_label without error."""
    task_id = uuid4()
    label_id = uuid4()
    project_id = uuid4()
    workspace_id = uuid4()
    user_id = uuid4()

    sample_project = Project(id=project_id, workspace_id=workspace_id, name="Project Alpha")
    sample_task = Task(id=task_id, project_id=project_id, title="Test Task")
    sample_task.project = sample_project
    sample_member = WorkspaceMember(
        workspace_id=workspace_id, user_id=user_id, role=WorkspaceRole.OWNER
    )

    sample_label = Label(id=label_id, project_id=project_id, name="Bug", color="#EF4444")
    existing_task_label = TaskLabel(task_id=task_id, label_id=label_id)

    label_service.task_repo.get_task_detail = AsyncMock(return_value=sample_task)
    label_service.workspace_repo.get_member = AsyncMock(return_value=sample_member)
    label_service.label_repo.get_by_id = AsyncMock(return_value=sample_label)
    label_service.label_repo.get_task_label = AsyncMock(return_value=existing_task_label)
    label_service.label_repo.assign_label_to_task = AsyncMock()

    task_label, label = await label_service.assign_label(task_id, label_id, user_id, is_admin=False)

    assert task_label == existing_task_label
    assert label == sample_label
    label_service.label_repo.assign_label_to_task.assert_not_called()


@pytest.mark.asyncio
async def test_assign_label_cross_project_raises_400(label_service: LabelService) -> None:
    """Test assigning label from different project raises 400 LABEL_NOT_IN_PROJECT."""

    task_id = uuid4()
    label_id = uuid4()
    project_id1 = uuid4()
    project_id2 = uuid4()
    workspace_id = uuid4()
    user_id = uuid4()

    sample_project = Project(id=project_id1, workspace_id=workspace_id, name="Project Alpha")
    sample_task = Task(id=task_id, project_id=project_id1, title="Test Task")
    sample_task.project = sample_project
    sample_member = WorkspaceMember(
        workspace_id=workspace_id, user_id=user_id, role=WorkspaceRole.OWNER
    )
    other_project_label = Label(id=label_id, project_id=project_id2, name="Other", color="#10B981")

    label_service.task_repo.get_task_detail = AsyncMock(return_value=sample_task)
    label_service.workspace_repo.get_member = AsyncMock(return_value=sample_member)
    label_service.label_repo.get_by_id = AsyncMock(return_value=other_project_label)

    with pytest.raises(ValidationError) as exc_info:
        await label_service.assign_label(task_id, label_id, user_id, is_admin=False)

    assert exc_info.value.code == "LABEL_NOT_IN_PROJECT"


@pytest.mark.asyncio
async def test_assign_label_viewer_raises_403(label_service: LabelService) -> None:
    """Test VIEWER assigning label raises ForbiddenError."""
    task_id = uuid4()
    label_id = uuid4()
    project_id = uuid4()
    workspace_id = uuid4()
    user_id = uuid4()

    sample_project = Project(id=project_id, workspace_id=workspace_id, name="Project Alpha")
    sample_task = Task(id=task_id, project_id=project_id, title="Test Task")
    sample_task.project = sample_project
    sample_member = WorkspaceMember(
        workspace_id=workspace_id, user_id=user_id, role=WorkspaceRole.VIEWER
    )

    label_service.task_repo.get_task_detail = AsyncMock(return_value=sample_task)
    label_service.workspace_repo.get_member = AsyncMock(return_value=sample_member)

    with pytest.raises(ForbiddenError) as exc_info:
        await label_service.assign_label(task_id, label_id, user_id, is_admin=False)

    assert exc_info.value.code == "FORBIDDEN"


@pytest.mark.asyncio
async def test_assign_label_non_member_raises_404(label_service: LabelService) -> None:
    """Test non-member assigning label raises NotFoundError (IDOR Guard)."""
    task_id = uuid4()
    label_id = uuid4()
    project_id = uuid4()
    workspace_id = uuid4()
    user_id = uuid4()

    sample_project = Project(id=project_id, workspace_id=workspace_id, name="Project Alpha")
    sample_task = Task(id=task_id, project_id=project_id, title="Test Task")
    sample_task.project = sample_project

    label_service.task_repo.get_task_detail = AsyncMock(return_value=sample_task)
    label_service.workspace_repo.get_member = AsyncMock(return_value=None)

    with pytest.raises(NotFoundError) as exc_info:
        await label_service.assign_label(task_id, label_id, user_id, is_admin=False)

    assert exc_info.value.code == "NOT_FOUND"


@pytest.mark.asyncio
async def test_remove_label_success(label_service: LabelService) -> None:
    """Test removing a label from a task successfully."""
    task_id = uuid4()
    label_id = uuid4()
    project_id = uuid4()
    workspace_id = uuid4()
    user_id = uuid4()

    sample_project = Project(id=project_id, workspace_id=workspace_id, name="Project Alpha")
    sample_task = Task(id=task_id, project_id=project_id, title="Test Task")
    sample_task.project = sample_project
    sample_member = WorkspaceMember(
        workspace_id=workspace_id, user_id=user_id, role=WorkspaceRole.OWNER
    )
    sample_label = Label(id=label_id, project_id=project_id, name="Bug", color="#EF4444")

    label_service.task_repo.get_task_detail = AsyncMock(return_value=sample_task)
    label_service.workspace_repo.get_member = AsyncMock(return_value=sample_member)
    label_service.label_repo.get_by_id = AsyncMock(return_value=sample_label)
    label_service.label_repo.remove_label_from_task = AsyncMock()

    await label_service.remove_label(task_id, label_id, user_id, is_admin=False)

    label_service.label_repo.remove_label_from_task.assert_called_once_with(task_id, label_id)


@pytest.mark.asyncio
async def test_remove_label_viewer_raises_403(label_service: LabelService) -> None:
    """Test VIEWER removing label raises ForbiddenError."""
    task_id = uuid4()
    label_id = uuid4()
    project_id = uuid4()
    workspace_id = uuid4()
    user_id = uuid4()

    sample_project = Project(id=project_id, workspace_id=workspace_id, name="Project Alpha")
    sample_task = Task(id=task_id, project_id=project_id, title="Test Task")
    sample_task.project = sample_project
    sample_member = WorkspaceMember(
        workspace_id=workspace_id, user_id=user_id, role=WorkspaceRole.VIEWER
    )

    label_service.task_repo.get_task_detail = AsyncMock(return_value=sample_task)
    label_service.workspace_repo.get_member = AsyncMock(return_value=sample_member)

    with pytest.raises(ForbiddenError) as exc_info:
        await label_service.remove_label(task_id, label_id, user_id, is_admin=False)

    assert exc_info.value.code == "FORBIDDEN"


@pytest.mark.asyncio
async def test_assign_label_editor_raises_403(label_service: LabelService) -> None:
    """Test EDITOR assigning label raises ForbiddenError per ADR-006."""
    task_id = uuid4()
    label_id = uuid4()
    project_id = uuid4()
    workspace_id = uuid4()
    user_id = uuid4()

    sample_project = Project(id=project_id, workspace_id=workspace_id, name="Project Alpha")
    sample_task = Task(id=task_id, project_id=project_id, title="Test Task")
    sample_task.project = sample_project
    sample_member = WorkspaceMember(
        workspace_id=workspace_id, user_id=user_id, role=WorkspaceRole.EDITOR
    )

    label_service.task_repo.get_task_detail = AsyncMock(return_value=sample_task)
    label_service.workspace_repo.get_member = AsyncMock(return_value=sample_member)

    with pytest.raises(ForbiddenError) as exc_info:
        await label_service.assign_label(task_id, label_id, user_id, is_admin=False)

    assert exc_info.value.code == "FORBIDDEN"


@pytest.mark.asyncio
async def test_remove_label_editor_raises_403(label_service: LabelService) -> None:
    """Test EDITOR removing label raises ForbiddenError per ADR-006."""
    task_id = uuid4()
    label_id = uuid4()
    project_id = uuid4()
    workspace_id = uuid4()
    user_id = uuid4()

    sample_project = Project(id=project_id, workspace_id=workspace_id, name="Project Alpha")
    sample_task = Task(id=task_id, project_id=project_id, title="Test Task")
    sample_task.project = sample_project
    sample_member = WorkspaceMember(
        workspace_id=workspace_id, user_id=user_id, role=WorkspaceRole.EDITOR
    )

    label_service.task_repo.get_task_detail = AsyncMock(return_value=sample_task)
    label_service.workspace_repo.get_member = AsyncMock(return_value=sample_member)

    with pytest.raises(ForbiddenError) as exc_info:
        await label_service.remove_label(task_id, label_id, user_id, is_admin=False)

    assert exc_info.value.code == "FORBIDDEN"


# === REDIS CACHE INVALIDATION UNIT TESTS ===


@pytest.mark.asyncio
async def test_assign_label_invalidates_redis_cache(label_service: LabelService) -> None:
    """Test assign_label invalidates project tasks cache pattern tasks:project:{project_id}:*."""
    task_id = uuid4()
    label_id = uuid4()
    project_id = uuid4()
    workspace_id = uuid4()
    user_id = uuid4()

    sample_project = Project(id=project_id, workspace_id=workspace_id, name="Project Alpha")
    sample_task = Task(id=task_id, project_id=project_id, title="Test Task")
    sample_task.project = sample_project
    sample_member = WorkspaceMember(
        workspace_id=workspace_id, user_id=user_id, role=WorkspaceRole.OWNER
    )
    sample_label = Label(id=label_id, project_id=project_id, name="Bug", color="#EF4444")
    created_task_label = TaskLabel(task_id=task_id, label_id=label_id)

    label_service.task_repo.get_task_detail = AsyncMock(return_value=sample_task)
    label_service.workspace_repo.get_member = AsyncMock(return_value=sample_member)
    label_service.label_repo.get_by_id = AsyncMock(return_value=sample_label)
    label_service.label_repo.get_task_label = AsyncMock(return_value=None)
    label_service.label_repo.assign_label_to_task = AsyncMock(return_value=created_task_label)

    mock_redis = AsyncMock()
    cache_key = f"tasks:project:{project_id}:page_1"
    mock_redis.keys = AsyncMock(return_value=[cache_key])
    mock_redis.delete = AsyncMock()
    label_service.redis = mock_redis

    await label_service.assign_label(task_id, label_id, user_id, is_admin=False)

    mock_redis.keys.assert_called_once_with(f"tasks:project:{project_id}:*")
    mock_redis.delete.assert_called_once_with(cache_key)


@pytest.mark.asyncio
async def test_remove_label_invalidates_redis_cache(label_service: LabelService) -> None:
    """Test remove_label invalidates project tasks cache pattern tasks:project:{project_id}:*."""
    task_id = uuid4()
    label_id = uuid4()
    project_id = uuid4()
    workspace_id = uuid4()
    user_id = uuid4()

    sample_project = Project(id=project_id, workspace_id=workspace_id, name="Project Alpha")
    sample_task = Task(id=task_id, project_id=project_id, title="Test Task")
    sample_task.project = sample_project
    sample_member = WorkspaceMember(
        workspace_id=workspace_id, user_id=user_id, role=WorkspaceRole.OWNER
    )
    sample_label = Label(id=label_id, project_id=project_id, name="Bug", color="#EF4444")

    label_service.task_repo.get_task_detail = AsyncMock(return_value=sample_task)
    label_service.workspace_repo.get_member = AsyncMock(return_value=sample_member)
    label_service.label_repo.get_by_id = AsyncMock(return_value=sample_label)
    label_service.label_repo.remove_label_from_task = AsyncMock()

    mock_redis = AsyncMock()
    cache_key = f"tasks:project:{project_id}:page_1"
    mock_redis.keys = AsyncMock(return_value=[cache_key])
    mock_redis.delete = AsyncMock()
    label_service.redis = mock_redis

    await label_service.remove_label(task_id, label_id, user_id, is_admin=False)

    mock_redis.keys.assert_called_once_with(f"tasks:project:{project_id}:*")
    mock_redis.delete.assert_called_once_with(cache_key)


@pytest.mark.asyncio
async def test_assign_label_redis_exception_handled(label_service: LabelService) -> None:
    """Test assign_label logs warning and doesn't fail if Redis raises an exception."""
    task_id = uuid4()
    label_id = uuid4()
    project_id = uuid4()
    workspace_id = uuid4()
    user_id = uuid4()

    sample_project = Project(id=project_id, workspace_id=workspace_id, name="Project Alpha")
    sample_task = Task(id=task_id, project_id=project_id, title="Test Task")
    sample_task.project = sample_project
    sample_member = WorkspaceMember(
        workspace_id=workspace_id, user_id=user_id, role=WorkspaceRole.OWNER
    )
    sample_label = Label(id=label_id, project_id=project_id, name="Bug", color="#EF4444")
    created_task_label = TaskLabel(task_id=task_id, label_id=label_id)

    label_service.task_repo.get_task_detail = AsyncMock(return_value=sample_task)
    label_service.workspace_repo.get_member = AsyncMock(return_value=sample_member)
    label_service.label_repo.get_by_id = AsyncMock(return_value=sample_label)
    label_service.label_repo.get_task_label = AsyncMock(return_value=None)
    label_service.label_repo.assign_label_to_task = AsyncMock(return_value=created_task_label)

    mock_redis = AsyncMock()
    mock_redis.keys = AsyncMock(side_effect=Exception("Redis error"))
    label_service.redis = mock_redis

    task_label, label = await label_service.assign_label(task_id, label_id, user_id, is_admin=False)

    assert task_label.task_id == task_id
    assert label.id == label_id
