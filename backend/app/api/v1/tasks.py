from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, status
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.core.redis import get_redis
from app.models.user import User
from app.schemas.common import SuccessResponse
from app.schemas.task import TaskCreateRequest, TaskResponse
from app.services.task import TaskService

router = APIRouter()


def get_task_service(
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
) -> TaskService:
    """Dependency providing TaskService instance."""
    return TaskService(db=db, redis=redis)


@router.post(
    "/projects/{project_id}/tasks",
    response_model=SuccessResponse[TaskResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Tạo công việc mới",
    description=(
        "Cho phép EDITOR và OWNER của workspace tạo công việc mới trong dự án, "
        "gán người phụ trách (bắt buộc phải là thành viên workspace) và "
        "thiết lập deadline/ưu tiên/mô tả."
    ),
    operation_id="taoCongViec",
)
async def create_task(
    project_id: UUID,
    body: TaskCreateRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    service: TaskService = Depends(get_task_service),
) -> SuccessResponse[TaskResponse]:
    """Create a new task within a project."""
    task = await service.create_task(
        project_id=project_id,
        current_user=current_user,
        dto=body,
        background_tasks=background_tasks,
    )
    return SuccessResponse(data=TaskResponse.model_validate(task))
