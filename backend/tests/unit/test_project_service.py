from datetime import UTC, datetime
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.core.exceptions import NotFoundError
from app.models.enums import ProjectStatus
from app.models.project import Project
from app.models.workspace import Workspace
from app.schemas.project import ProjectCreateRequest
from app.services.project import ProjectService


@pytest.fixture
def mock_db() -> AsyncMock:
    """Mock AsyncSession for unit testing."""
    return AsyncMock()


@pytest.fixture
def project_service(mock_db: AsyncMock) -> ProjectService:
    """Instantiate ProjectService with mock AsyncSession."""
    return ProjectService(db=mock_db)


@pytest.mark.asyncio
async def test_create_project_success(project_service: ProjectService) -> None:
    """Test creating a project successfully when workspace exists."""
    workspace_id = uuid4()
    sample_workspace = Workspace(id=workspace_id, name="Test Workspace", owner_id=uuid4())
    created_project = Project(
        id=uuid4(),
        workspace_id=workspace_id,
        name="Website Redesign",
        description="Redesigning corporate website",
        status=ProjectStatus.ACTIVE,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )

    project_service.workspace_repo.get_by_id = AsyncMock(return_value=sample_workspace)
    project_service.project_repo.create_project = AsyncMock(return_value=created_project)

    dto = ProjectCreateRequest(name="Website Redesign", description="Redesigning corporate website")
    result = await project_service.create_project(workspace_id, dto)

    project_service.workspace_repo.get_by_id.assert_called_once_with(workspace_id)
    project_service.project_repo.create_project.assert_called_once_with(
        workspace_id=workspace_id,
        name="Website Redesign",
        description="Redesigning corporate website",
        status=ProjectStatus.ACTIVE,
    )
    assert result.id == created_project.id
    assert result.name == "Website Redesign"
    assert result.status == ProjectStatus.ACTIVE


@pytest.mark.asyncio
async def test_create_project_workspace_not_found(project_service: ProjectService) -> None:
    """Test creating a project when workspace does not exist raises NotFoundError."""
    workspace_id = uuid4()
    project_service.workspace_repo.get_by_id = AsyncMock(return_value=None)

    dto = ProjectCreateRequest(name="Website Redesign", description="Test desc")
    with pytest.raises(NotFoundError) as exc_info:
        await project_service.create_project(workspace_id, dto)

    assert exc_info.value.code == "NOT_FOUND"
    assert "Workspace không tồn tại" in exc_info.value.message


@pytest.mark.asyncio
async def test_list_projects_success(project_service: ProjectService) -> None:
    """Test listing projects returns items and total count."""
    workspace_id = uuid4()
    user_id = uuid4()
    sample_workspace = Workspace(id=workspace_id, name="Test Workspace", owner_id=uuid4())
    project1 = Project(
        id=uuid4(),
        workspace_id=workspace_id,
        name="Project 1",
        status=ProjectStatus.ACTIVE,
        created_at=datetime.now(UTC),
    )

    project_service.workspace_repo.get_by_id = AsyncMock(return_value=sample_workspace)
    project_service.workspace_repo.get_member = AsyncMock(return_value=AsyncMock())
    project_service.project_repo.list_by_workspace_with_task_count = AsyncMock(
        return_value=([(project1, 5)], 1)
    )

    items, total = await project_service.list_projects(
        workspace_id=workspace_id,
        current_user_id=user_id,
        is_admin=False,
        status=ProjectStatus.ACTIVE,
        page=1,
        limit=20,
    )

    assert total == 1
    assert len(items) == 1
    assert items[0][0].name == "Project 1"
    assert items[0][1] == 5
    project_service.project_repo.list_by_workspace_with_task_count.assert_called_once_with(
        workspace_id=workspace_id, status=ProjectStatus.ACTIVE, skip=0, limit=20
    )


@pytest.mark.asyncio
async def test_list_projects_empty(project_service: ProjectService) -> None:
    """Test listing projects returns empty list when no projects exist."""
    workspace_id = uuid4()
    user_id = uuid4()
    sample_workspace = Workspace(id=workspace_id, name="Test Workspace", owner_id=uuid4())

    project_service.workspace_repo.get_by_id = AsyncMock(return_value=sample_workspace)
    project_service.workspace_repo.get_member = AsyncMock(return_value=AsyncMock())
    project_service.project_repo.list_by_workspace_with_task_count = AsyncMock(return_value=([], 0))

    items, total = await project_service.list_projects(
        workspace_id=workspace_id, current_user_id=user_id
    )

    assert total == 0
    assert len(items) == 0


@pytest.mark.asyncio
async def test_list_projects_workspace_not_found(project_service: ProjectService) -> None:
    """Test listing projects when workspace does not exist raises NotFoundError."""
    workspace_id = uuid4()
    user_id = uuid4()
    project_service.workspace_repo.get_by_id = AsyncMock(return_value=None)

    with pytest.raises(NotFoundError) as exc_info:
        await project_service.list_projects(workspace_id=workspace_id, current_user_id=user_id)

    assert exc_info.value.code == "NOT_FOUND"
    assert "Workspace không tồn tại" in exc_info.value.message


@pytest.mark.asyncio
async def test_list_projects_non_member_404(project_service: ProjectService) -> None:
    """Test listing projects when user is not a member raises NotFoundError (404 Guard)."""
    workspace_id = uuid4()
    user_id = uuid4()
    sample_workspace = Workspace(id=workspace_id, name="Test Workspace", owner_id=uuid4())

    project_service.workspace_repo.get_by_id = AsyncMock(return_value=sample_workspace)
    project_service.workspace_repo.get_member = AsyncMock(return_value=None)

    with pytest.raises(NotFoundError) as exc_info:
        await project_service.list_projects(
            workspace_id=workspace_id, current_user_id=user_id, is_admin=False
        )

    assert exc_info.value.code == "NOT_FOUND"
    assert "Workspace không tồn tại" in exc_info.value.message


@pytest.mark.asyncio
async def test_get_project_detail_success(project_service: ProjectService) -> None:
    """Test retrieving project detail successfully for a member."""
    project_id = uuid4()
    workspace_id = uuid4()
    user_id = uuid4()
    sample_project = Project(
        id=project_id,
        workspace_id=workspace_id,
        name="Detail Project",
        status=ProjectStatus.ACTIVE,
        created_at=datetime.now(UTC),
    )

    project_service.project_repo.get_detail_with_task_count = AsyncMock(
        return_value=(sample_project, 3)
    )
    project_service.workspace_repo.get_member = AsyncMock(return_value=AsyncMock())

    project, task_count = await project_service.get_project_detail(
        project_id=project_id, current_user_id=user_id, is_admin=False
    )

    assert project.id == project_id
    assert task_count == 3
    project_service.workspace_repo.get_member.assert_called_once_with(workspace_id, user_id)


@pytest.mark.asyncio
async def test_get_project_detail_idor_protection(project_service: ProjectService) -> None:
    """Test non-member user accessing project raises NotFoundError (404 Guard against IDOR)."""
    project_id = uuid4()
    workspace_id = uuid4()
    user_id = uuid4()
    sample_project = Project(
        id=project_id,
        workspace_id=workspace_id,
        name="Secret Project",
        status=ProjectStatus.ACTIVE,
        created_at=datetime.now(UTC),
    )

    project_service.project_repo.get_detail_with_task_count = AsyncMock(
        return_value=(sample_project, 0)
    )
    project_service.workspace_repo.get_member = AsyncMock(return_value=None)

    with pytest.raises(NotFoundError) as exc_info:
        await project_service.get_project_detail(
            project_id=project_id, current_user_id=user_id, is_admin=False
        )

    assert exc_info.value.code == "NOT_FOUND"
    assert "Project không tồn tại" in exc_info.value.message
