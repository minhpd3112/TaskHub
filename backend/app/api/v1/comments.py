from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.schemas.comment import CommentCreateRequest, CommentResponse
from app.schemas.common import SuccessResponse
from app.services.comment import CommentService

router = APIRouter(prefix="/tasks", tags=["Comments"])


def get_comment_service(
    db: AsyncSession = Depends(get_db),
) -> CommentService:
    """Dependency providing CommentService instance."""
    return CommentService(db=db)


@router.post(
    "/{task_id}/comments",
    response_model=SuccessResponse[CommentResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Thêm bình luận vào công việc",
    description=(
        "Cho phép tất cả thành viên trong workspace (OWNER, EDITOR, VIEWER) và System ADMIN"
        " thêm bình luận."
    ),
    operation_id="taoBinhLuan",
)
async def create_comment(
    task_id: UUID,
    dto: CommentCreateRequest,
    current_user: User = Depends(get_current_user),
    service: CommentService = Depends(get_comment_service),
) -> SuccessResponse[CommentResponse]:
    """Add a new comment to a task."""
    comment = await service.create_comment(
        task_id=task_id,
        current_user=current_user,
        content=dto.content,
    )
    return SuccessResponse(data=CommentResponse.model_validate(comment))
