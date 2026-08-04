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


@pytest.mark.asyncio
async def test_invite_member_success(
    workspace_service: WorkspaceService, sample_user: User
) -> None:
    """Test invite_member creates new WorkspaceMember record successfully."""
    ws_id = uuid4()
    target_user_id = uuid4()
    now = datetime.now(UTC)

    ws = Workspace(id=ws_id, name="WS", owner_id=sample_user.id, created_at=now)
    owner_member = WorkspaceMember(
        workspace_id=ws_id, user_id=sample_user.id, role=WorkspaceRole.OWNER, joined_at=now
    )
    target_user = User(
        id=target_user_id,
        email="invitee@taskhub.io",
        full_name="Invitee",
        hashed_password="hash",
        role=UserRole.MEMBER,
        is_active=True,
    )
    new_member = WorkspaceMember(
        workspace_id=ws_id, user_id=target_user_id, role=WorkspaceRole.EDITOR, joined_at=now
    )

    workspace_service.workspace_repo.get_by_id = AsyncMock(return_value=ws)
    workspace_service.workspace_member_repo.get_member = AsyncMock(
        side_effect=lambda w_id, u_id: owner_member if u_id == sample_user.id else None
    )
    workspace_service.user_repo.get_by_email = AsyncMock(return_value=target_user)
    workspace_service.workspace_member_repo.add_member = AsyncMock(return_value=new_member)

    from app.schemas.workspace import MemberInviteRequest

    dto = MemberInviteRequest(email="invitee@taskhub.io", role=WorkspaceRole.EDITOR)
    res = await workspace_service.invite_member(sample_user, ws_id, dto)

    assert res.workspace_id == ws_id
    assert res.user_id == target_user_id
    assert res.role == WorkspaceRole.EDITOR


@pytest.mark.asyncio
async def test_invite_member_user_not_found(
    workspace_service: WorkspaceService, sample_user: User
) -> None:
    """Test invite_member raises NotFoundError (code USER_NOT_FOUND)."""
    ws_id = uuid4()
    ws = Workspace(id=ws_id, name="WS", owner_id=sample_user.id, created_at=datetime.now(UTC))
    owner_member = WorkspaceMember(
        workspace_id=ws_id,
        user_id=sample_user.id,
        role=WorkspaceRole.OWNER,
        joined_at=datetime.now(UTC),
    )

    workspace_service.workspace_repo.get_by_id = AsyncMock(return_value=ws)
    workspace_service.workspace_member_repo.get_member = AsyncMock(return_value=owner_member)
    workspace_service.user_repo.get_by_email = AsyncMock(return_value=None)

    from app.core.exceptions import NotFoundError
    from app.schemas.workspace import MemberInviteRequest

    dto = MemberInviteRequest(email="nonexistent@taskhub.io")
    with pytest.raises(NotFoundError) as exc_info:
        await workspace_service.invite_member(sample_user, ws_id, dto)

    assert exc_info.value.code == "USER_NOT_FOUND"


@pytest.mark.asyncio
async def test_invite_member_already_member(
    workspace_service: WorkspaceService, sample_user: User
) -> None:
    """Test invite_member raises ConflictError (code ALREADY_MEMBER)."""
    ws_id = uuid4()
    target_id = uuid4()
    ws = Workspace(id=ws_id, name="WS", owner_id=sample_user.id, created_at=datetime.now(UTC))
    owner_member = WorkspaceMember(
        workspace_id=ws_id,
        user_id=sample_user.id,
        role=WorkspaceRole.OWNER,
        joined_at=datetime.now(UTC),
    )
    target_user = User(
        id=target_id,
        email="member@taskhub.io",
        full_name="Member",
        hashed_password="hash",
        role=UserRole.MEMBER,
    )
    existing_member = WorkspaceMember(
        workspace_id=ws_id,
        user_id=target_id,
        role=WorkspaceRole.VIEWER,
        joined_at=datetime.now(UTC),
    )

    workspace_service.workspace_repo.get_by_id = AsyncMock(return_value=ws)
    workspace_service.workspace_member_repo.get_member = AsyncMock(
        side_effect=lambda w_id, u_id: owner_member if u_id == sample_user.id else existing_member
    )
    workspace_service.user_repo.get_by_email = AsyncMock(return_value=target_user)

    from app.core.exceptions import ConflictError
    from app.schemas.workspace import MemberInviteRequest

    dto = MemberInviteRequest(email="member@taskhub.io")
    with pytest.raises(ConflictError) as exc_info:
        await workspace_service.invite_member(sample_user, ws_id, dto)

    assert exc_info.value.code == "ALREADY_MEMBER"


@pytest.mark.asyncio
async def test_update_member_role_demote_last_owner(
    workspace_service: WorkspaceService, sample_user: User
) -> None:
    """Test updating role of last OWNER raises ValidationError (code CANNOT_DEMOTE_LAST_OWNER)."""
    ws_id = uuid4()
    ws = Workspace(id=ws_id, name="WS", owner_id=sample_user.id, created_at=datetime.now(UTC))
    owner_member = WorkspaceMember(
        workspace_id=ws_id,
        user_id=sample_user.id,
        role=WorkspaceRole.OWNER,
        joined_at=datetime.now(UTC),
    )

    workspace_service.workspace_repo.get_by_id = AsyncMock(return_value=ws)
    workspace_service.workspace_member_repo.get_member = AsyncMock(return_value=owner_member)
    workspace_service.workspace_member_repo.count_owners = AsyncMock(return_value=1)

    from app.core.exceptions import ValidationError
    from app.schemas.workspace import MemberUpdateRoleRequest

    dto = MemberUpdateRoleRequest(role=WorkspaceRole.EDITOR)
    with pytest.raises(ValidationError) as exc_info:
        await workspace_service.update_member_role(sample_user, ws_id, sample_user.id, dto)

    assert exc_info.value.code == "CANNOT_DEMOTE_LAST_OWNER"


@pytest.mark.asyncio
async def test_remove_member_last_owner(
    workspace_service: WorkspaceService, sample_user: User
) -> None:
    """Test removing last OWNER raises ValidationError (code CANNOT_REMOVE_OWNER)."""
    ws_id = uuid4()
    ws = Workspace(id=ws_id, name="WS", owner_id=sample_user.id, created_at=datetime.now(UTC))
    owner_member = WorkspaceMember(
        workspace_id=ws_id,
        user_id=sample_user.id,
        role=WorkspaceRole.OWNER,
        joined_at=datetime.now(UTC),
    )

    workspace_service.workspace_repo.get_by_id = AsyncMock(return_value=ws)
    workspace_service.workspace_member_repo.get_member = AsyncMock(return_value=owner_member)
    workspace_service.workspace_member_repo.count_owners = AsyncMock(return_value=1)

    from app.core.exceptions import ValidationError

    with pytest.raises(ValidationError) as exc_info:
        await workspace_service.remove_member(sample_user, ws_id, sample_user.id)

    assert exc_info.value.code == "CANNOT_REMOVE_OWNER"


@pytest.mark.asyncio
async def test_remove_member_success_reassigns_tasks(
    workspace_service: WorkspaceService, sample_user: User
) -> None:
    """Test remove_member reassigns tasks to workspace owner and deletes member record."""
    ws_id = uuid4()
    target_user_id = uuid4()
    now = datetime.now(UTC)

    ws = Workspace(id=ws_id, name="WS", owner_id=sample_user.id, created_at=now)
    owner_member = WorkspaceMember(
        workspace_id=ws_id, user_id=sample_user.id, role=WorkspaceRole.OWNER, joined_at=now
    )
    target_member = WorkspaceMember(
        workspace_id=ws_id, user_id=target_user_id, role=WorkspaceRole.EDITOR, joined_at=now
    )

    workspace_service.workspace_repo.get_by_id = AsyncMock(return_value=ws)
    workspace_service.workspace_member_repo.get_member = AsyncMock(
        side_effect=lambda w_id, u_id: owner_member if u_id == sample_user.id else target_member
    )
    workspace_service.workspace_member_repo.reassign_workspace_member_tasks = AsyncMock(
        return_value=2
    )
    workspace_service.workspace_member_repo.remove_member = AsyncMock()

    await workspace_service.remove_member(sample_user, ws_id, target_user_id)

    workspace_service.workspace_member_repo.reassign_workspace_member_tasks.assert_called_once_with(
        workspace_id=ws_id,
        member_id=target_user_id,
        new_assignee_id=sample_user.id,
    )
    workspace_service.workspace_member_repo.remove_member.assert_called_once_with(
        ws_id, target_user_id
    )
    workspace_service.db.commit.assert_called_once()


@pytest.mark.asyncio
async def test_update_workspace_success_as_owner(
    workspace_service: WorkspaceService, sample_user: User
) -> None:
    """Test OWNER can update workspace name successfully."""
    ws_id = uuid4()
    now = datetime.now(UTC)
    ws = Workspace(id=ws_id, name="Old Name", owner_id=sample_user.id, created_at=now)
    owner_member = WorkspaceMember(
        workspace_id=ws_id, user_id=sample_user.id, role=WorkspaceRole.OWNER, joined_at=now
    )
    updated_ws = Workspace(id=ws_id, name="New Name", owner_id=sample_user.id, created_at=now)

    workspace_service.workspace_repo.get_by_id = AsyncMock(return_value=ws)
    workspace_service.workspace_member_repo.get_member = AsyncMock(return_value=owner_member)
    workspace_service.workspace_repo.update_workspace = AsyncMock(return_value=updated_ws)

    from app.schemas.workspace import WorkspaceUpdateRequest

    dto = WorkspaceUpdateRequest(name="New Name")
    response = await workspace_service.update_workspace(sample_user, ws_id, dto)

    workspace_service.workspace_repo.update_workspace.assert_called_once_with(ws_id, "New Name")
    workspace_service.db.commit.assert_called_once()
    assert response.name == "New Name"


@pytest.mark.asyncio
async def test_update_workspace_success_as_admin(
    workspace_service: WorkspaceService, sample_user: User
) -> None:
    """Test system ADMIN can update workspace name successfully even if not a member."""
    admin_user = User(
        id=uuid4(),
        email="admin@taskhub.io",
        full_name="System Admin",
        hashed_password="hash",
        role=UserRole.ADMIN,
        is_active=True,
    )
    ws_id = uuid4()
    now = datetime.now(UTC)
    ws = Workspace(id=ws_id, name="Old Name", owner_id=sample_user.id, created_at=now)
    updated_ws = Workspace(
        id=ws_id, name="Updated By Admin", owner_id=sample_user.id, created_at=now
    )

    workspace_service.workspace_repo.get_by_id = AsyncMock(return_value=ws)
    workspace_service.workspace_repo.update_workspace = AsyncMock(return_value=updated_ws)

    from app.schemas.workspace import WorkspaceUpdateRequest

    dto = WorkspaceUpdateRequest(name="Updated By Admin")
    response = await workspace_service.update_workspace(admin_user, ws_id, dto)

    workspace_service.workspace_repo.update_workspace.assert_called_once_with(
        ws_id, "Updated By Admin"
    )
    assert response.name == "Updated By Admin"


@pytest.mark.asyncio
async def test_update_workspace_forbidden_as_editor_or_viewer(
    workspace_service: WorkspaceService, sample_user: User
) -> None:
    """Test EDITOR or VIEWER role gets ForbiddenError when updating workspace name."""
    editor_user = User(
        id=uuid4(),
        email="editor@taskhub.io",
        full_name="Editor User",
        hashed_password="hash",
        role=UserRole.MEMBER,
        is_active=True,
    )
    ws_id = uuid4()
    now = datetime.now(UTC)
    ws = Workspace(id=ws_id, name="Workspace Name", owner_id=sample_user.id, created_at=now)
    editor_member = WorkspaceMember(
        workspace_id=ws_id, user_id=editor_user.id, role=WorkspaceRole.EDITOR, joined_at=now
    )

    workspace_service.workspace_repo.get_by_id = AsyncMock(return_value=ws)
    workspace_service.workspace_member_repo.get_member = AsyncMock(return_value=editor_member)

    from app.core.exceptions import ForbiddenError
    from app.schemas.workspace import WorkspaceUpdateRequest

    dto = WorkspaceUpdateRequest(name="Unauthorized Name Change")
    with pytest.raises(ForbiddenError) as exc_info:
        await workspace_service.update_workspace(editor_user, ws_id, dto)

    assert exc_info.value.code == "FORBIDDEN"


@pytest.mark.asyncio
async def test_update_workspace_not_found(
    workspace_service: WorkspaceService, sample_user: User
) -> None:
    """Test update_workspace raises NotFoundError when workspace does not exist."""
    workspace_service.workspace_repo.get_by_id = AsyncMock(return_value=None)

    from app.core.exceptions import NotFoundError
    from app.schemas.workspace import WorkspaceUpdateRequest

    dto = WorkspaceUpdateRequest(name="Any Name")
    with pytest.raises(NotFoundError) as exc_info:
        await workspace_service.update_workspace(sample_user, uuid4(), dto)

    assert exc_info.value.code == "NOT_FOUND"


@pytest.mark.asyncio
async def test_delete_workspace_success_as_owner(
    workspace_service: WorkspaceService, sample_user: User
) -> None:
    """Test OWNER can delete workspace successfully."""
    ws_id = uuid4()
    now = datetime.now(UTC)
    ws = Workspace(id=ws_id, name="To Delete", owner_id=sample_user.id, created_at=now)
    owner_member = WorkspaceMember(
        workspace_id=ws_id, user_id=sample_user.id, role=WorkspaceRole.OWNER, joined_at=now
    )

    workspace_service.workspace_repo.get_by_id = AsyncMock(return_value=ws)
    workspace_service.workspace_member_repo.get_member = AsyncMock(return_value=owner_member)
    workspace_service.workspace_repo.delete_by_id = AsyncMock(return_value=True)

    await workspace_service.delete_workspace(sample_user, ws_id)

    workspace_service.workspace_repo.delete_by_id.assert_called_once_with(ws_id)
    workspace_service.db.commit.assert_called_once()


@pytest.mark.asyncio
async def test_delete_workspace_forbidden_for_non_owner(
    workspace_service: WorkspaceService, sample_user: User
) -> None:
    """Test EDITOR role gets ForbiddenError when attempting to delete workspace."""
    editor_user = User(
        id=uuid4(),
        email="editor@taskhub.io",
        full_name="Editor",
        hashed_password="hash",
        role=UserRole.MEMBER,
        is_active=True,
    )
    ws_id = uuid4()
    now = datetime.now(UTC)
    ws = Workspace(id=ws_id, name="WS", owner_id=sample_user.id, created_at=now)
    editor_member = WorkspaceMember(
        workspace_id=ws_id, user_id=editor_user.id, role=WorkspaceRole.EDITOR, joined_at=now
    )

    workspace_service.workspace_repo.get_by_id = AsyncMock(return_value=ws)
    workspace_service.workspace_member_repo.get_member = AsyncMock(return_value=editor_member)

    from app.core.exceptions import ForbiddenError

    with pytest.raises(ForbiddenError) as exc_info:
        await workspace_service.delete_workspace(editor_user, ws_id)

    assert exc_info.value.code == "FORBIDDEN"


@pytest.mark.asyncio
async def test_delete_workspace_not_found(
    workspace_service: WorkspaceService, sample_user: User
) -> None:
    """Test delete_workspace raises NotFoundError when workspace does not exist."""
    workspace_service.workspace_repo.get_by_id = AsyncMock(return_value=None)

    from app.core.exceptions import NotFoundError

    with pytest.raises(NotFoundError) as exc_info:
        await workspace_service.delete_workspace(sample_user, uuid4())

    assert exc_info.value.code == "NOT_FOUND"
