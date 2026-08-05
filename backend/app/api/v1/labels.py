from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.enums import UserRole
from app.models.user import User
from app.schemas.common import SuccessResponse
from app.schemas.label import LabelCreateRequest, LabelResponse
from app.services.label import LabelService

router = APIRouter(prefix="/projects", tags=["Labels"])


def get_label_service(
    db: AsyncSession = Depends(get_db),
) -> LabelService:
    """Dependency providing LabelService instance."""
    return LabelService(db=db)


@router.post(
    "/{project_id}/labels",
    response_model=SuccessResponse[LabelResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Tạo nhãn mới trong dự án",
    description="Cho phép EDITOR hoặc OWNER (hoặc System ADMIN) tạo nhãn cho dự án.",
    operation_id="taoNhan",
)
async def create_label(
    project_id: UUID,
    dto: LabelCreateRequest,
    current_user: User = Depends(get_current_user),
    service: LabelService = Depends(get_label_service),
) -> SuccessResponse[LabelResponse]:
    """Create a new label within a project."""
    label = await service.create_label(
        project_id=project_id,
        dto=dto,
        current_user_id=current_user.id,
        is_admin=(current_user.role == UserRole.ADMIN),
    )
    return SuccessResponse(data=LabelResponse.model_validate(label))


@router.get(
    "/{project_id}/labels",
    response_model=SuccessResponse[list[LabelResponse]],
    status_code=status.HTTP_200_OK,
    summary="Xem danh sách nhãn của dự án",
    description=(
        "Cho phép mọi thành viên trong Workspace (VIEWER, EDITOR, OWNER) và System ADMIN xem"
        " danh sách nhãn."
    ),
    operation_id="lietKeNhan",
)
async def list_labels(
    project_id: UUID,
    current_user: User = Depends(get_current_user),
    service: LabelService = Depends(get_label_service),
) -> SuccessResponse[list[LabelResponse]]:
    """Retrieve all labels of a project."""
    labels = await service.list_labels(
        project_id=project_id,
        current_user_id=current_user.id,
        is_admin=(current_user.role == UserRole.ADMIN),
    )
    data = [LabelResponse.model_validate(lbl) for lbl in labels]
    return SuccessResponse(data=data)
