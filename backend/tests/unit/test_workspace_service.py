from datetime import UTC, datetime
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.models.enums import UserRole, WorkspaceRole
from app.models.user import User
from app.models.workspace import Workspace, WorkspaceMember
from app.schemas.workspace import WorkspaceCreateRequest
from app.services.workspace import WorkspaceService


@pytest.fixture
def mock_db() -> AsyncMock:
    """Mock AsyncSession for unit testing."""
    return AsyncMock()


@pytest.fixture
def workspace_service(mock_db: AsyncMock) -> WorkspaceService:
    """Instantiate WorkspaceService with mock AsyncSession."""
    return WorkspaceService(db=mock_db)


@pytest.fixture
def sample_user() -> User:
    """Sample User instance for unit testing."""
    return User(
        id=uuid4(),
        email="owner@taskhub.io",
        full_name="Workspace Owner",
        hashed_password="hashed_password",
        role=UserRole.MEMBER,
        is_active=True,
        created_at=datetime.now(UTC),
    )


@pytest.mark.asyncio
async def test_create_workspace_success(
    workspace_service: WorkspaceService, sample_user: User
) -> None:
    """Test creating workspace and assigning OWNER member role."""
    workspace_id = uuid4()
    created_ws = Workspace(
        id=workspace_id,
        name="Engineering Team",
        owner_id=sample_user.id,
        created_at=datetime.now(UTC),
    )
    created_member = WorkspaceMember(
        workspace_id=workspace_id,
        user_id=sample_user.id,
        role=WorkspaceRole.OWNER,
        joined_at=datetime.now(UTC),
    )

    workspace_service.workspace_repo.create_workspace = AsyncMock(return_value=created_ws)
    workspace_service.workspace_member_repo.add_member = AsyncMock(return_value=created_member)

    dto = WorkspaceCreateRequest(name="Engineering Team")
    response = await workspace_service.create_workspace(sample_user, dto)

    workspace_service.workspace_repo.create_workspace.assert_called_once_with(
        name="Engineering Team",
        owner_id=sample_user.id,
    )
    workspace_service.workspace_member_repo.add_member.assert_called_once_with(
        workspace_id=workspace_id,
        user_id=sample_user.id,
        role=WorkspaceRole.OWNER,
    )
    workspace_service.db.commit.assert_called_once()
    workspace_service.db.refresh.assert_called_once_with(created_ws)

    assert response.id == workspace_id
    assert response.name == "Engineering Team"
    assert response.owner_id == sample_user.id


@pytest.mark.asyncio
async def test_get_user_workspaces_empty(
    workspace_service: WorkspaceService, sample_user: User
) -> None:
    """Test get_user_workspaces returns empty list when user is not a member of any workspace."""
    workspace_service.workspace_repo.get_workspaces_by_user_id = AsyncMock(return_value=[])

    response = await workspace_service.get_user_workspaces(sample_user)

    workspace_service.workspace_repo.get_workspaces_by_user_id.assert_called_once_with(
        sample_user.id
    )
    assert response == []


@pytest.mark.asyncio
async def test_get_user_workspaces_success(
    workspace_service: WorkspaceService, sample_user: User
) -> None:
    """Test get_user_workspaces returns workspace items with user roles (OWNER, EDITOR, VIEWER)."""
    ws1_id = uuid4()
    ws2_id = uuid4()
    ws3_id = uuid4()
    now = datetime.now(UTC)

    ws1 = Workspace(id=ws1_id, name="WS Owner", owner_id=sample_user.id, created_at=now)
    ws2 = Workspace(id=ws2_id, name="WS Editor", owner_id=uuid4(), created_at=now)
    ws3 = Workspace(id=ws3_id, name="WS Viewer", owner_id=uuid4(), created_at=now)

    mock_items = [
        (ws1, WorkspaceRole.OWNER),
        (ws2, WorkspaceRole.EDITOR),
        (ws3, WorkspaceRole.VIEWER),
    ]

    workspace_service.workspace_repo.get_workspaces_by_user_id = AsyncMock(return_value=mock_items)

    response = await workspace_service.get_user_workspaces(sample_user)

    workspace_service.workspace_repo.get_workspaces_by_user_id.assert_called_once_with(
        sample_user.id
    )
    assert len(response) == 3
    assert response[0].id == ws1_id
    assert response[0].role == WorkspaceRole.OWNER
    assert response[1].id == ws2_id
    assert response[1].role == WorkspaceRole.EDITOR
    assert response[2].id == ws3_id
    assert response[2].role == WorkspaceRole.VIEWER
