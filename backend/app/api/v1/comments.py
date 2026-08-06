from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.schemas.comment import CommentCreateRequest, CommentResponse
from app.schemas.common import PaginatedResponse, SuccessResponse
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


@router.get(
    "/{task_id}/comments",
    response_model=PaginatedResponse[CommentResponse],
    status_code=status.HTTP_200_OK,
    summary="Xem danh sách bình luận của công việc",
    description=(
        "Cho phép tất cả thành viên trong workspace (OWNER, EDITOR, VIEWER) và System ADMIN"
        " xem danh sách bình luận của công việc (sắp xếp tăng dần theo thời gian)."
    ),
    operation_id="lietKeBinhLuan",
)
async def list_comments(
    task_id: UUID,
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=50, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    service: CommentService = Depends(get_comment_service),
) -> PaginatedResponse[CommentResponse]:
    """Get list of comments for a task."""
    return await service.list_comments(
        task_id=task_id,
        current_user=current_user,
        page=page,
        limit=limit,
    )


@router.delete(
    "/{task_id}/comments/{comment_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Xóa bình luận",
    description=(
        "Cho phép tác giả xóa bình luận của mình, OWNER/EDITOR workspace hoặc System ADMIN"
        " xóa bất kỳ bình luận nào trong dự án."
    ),
    operation_id="xoaBinhLuan",
)
async def delete_comment(
    task_id: UUID,
    comment_id: UUID,
    current_user: User = Depends(get_current_user),
    service: CommentService = Depends(get_comment_service),
) -> None:
    """Delete a comment from a task."""
    await service.delete_comment(
        task_id=task_id,
        comment_id=comment_id,
        current_user=current_user,
    )
