from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.core.exceptions import ConflictError, ForbiddenError, NotFoundError
from app.models.enums import WorkspaceRole
from app.models.label import Label
from app.models.project import Project
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
async def test_create_label_success_editor(label_service: LabelService) -> None:
    """Test EDITOR creates a label successfully."""
    project_id = uuid4()
    user_id = uuid4()
    workspace_id = uuid4()

    sample_project = Project(id=project_id, workspace_id=workspace_id, name="Project Alpha")
    sample_member = WorkspaceMember(
        workspace_id=workspace_id, user_id=user_id, role=WorkspaceRole.EDITOR
    )
    created_label = Label(id=uuid4(), project_id=project_id, name="Feature", color="#3B82F6")

    label_service.project_repo.get_by_id = AsyncMock(return_value=sample_project)
    label_service.workspace_repo.get_member = AsyncMock(return_value=sample_member)
    label_service.label_repo.get_by_project_and_name = AsyncMock(return_value=None)
    label_service.label_repo.create_label = AsyncMock(return_value=created_label)

    dto = LabelCreateRequest(name="Feature", color="#3B82F6")
    result = await label_service.create_label(project_id, dto, user_id, is_admin=False)

    assert result.name == "Feature"


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
