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
