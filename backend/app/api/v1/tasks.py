from datetime import date
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, Query, status
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.core.redis import get_redis
from app.models.enums import TaskPriority, TaskStatus
from app.models.user import User
from app.schemas.common import PaginatedResponse, SuccessResponse
from app.schemas.task import (
    TaskCreateRequest,
    TaskDetailResponse,
    TaskPriorityUpdateRequest,
    TaskResponse,
    TaskStatusUpdateRequest,
    TaskUpdateRequest,
)
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
        "Cho phép thành viên có vai trò OWNER (hoặc System ADMIN) tạo công việc mới trong dự án, "
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


@router.get(
    "/projects/{project_id}/tasks",
    response_model=PaginatedResponse[TaskResponse],
    status_code=status.HTTP_200_OK,
    summary="Xem danh sách công việc của dự án",
    description=(
        "Xem danh sách các công việc thuộc dự án với bộ lọc status, priority, "
        "assignee, due_date và phân trang. "
        "EDITOR chỉ nhìn thấy task được phân công cho mình."
    ),
    operation_id="lietKeCongViec",
)
async def list_tasks(
    project_id: UUID,
    status: TaskStatus | None = Query(default=None, description="Lọc theo trạng thái"),
    priority: TaskPriority | None = Query(default=None, description="Lọc theo độ ưu tiên"),
    assignee_id: UUID | None = Query(default=None, description="Lọc theo UUID người phụ trách"),
    due_date: date | None = Query(default=None, description="Lọc theo hạn hoàn thành (YYYY-MM-DD)"),
    page: int = Query(default=1, ge=1, description="Trang hiện tại"),
    limit: int = Query(default=20, ge=1, le=100, description="Số bản ghi trên mỗi trang (1-100)"),
    current_user: User = Depends(get_current_user),
    service: TaskService = Depends(get_task_service),
) -> PaginatedResponse[TaskResponse]:
    """List tasks in a project with pagination, filtering, and RBAC scoping."""
    return await service.list_tasks(
        project_id=project_id,
        current_user=current_user,
        status=status,
        priority=priority,
        assignee_id=assignee_id,
        due_date=due_date,
        page=page,
        limit=limit,
    )


@router.get(
    "/tasks/{task_id}",
    response_model=SuccessResponse[TaskDetailResponse],
    status_code=status.HTTP_200_OK,
    summary="Xem chi tiết công việc",
    description=(
        "Xem thông tin chi tiết một công việc gồm người phụ trách, "
        "người tạo, các nhãn và bình luận."
    ),
    operation_id="layCongViec",
)
async def get_task_detail(
    task_id: UUID,
    current_user: User = Depends(get_current_user),
    service: TaskService = Depends(get_task_service),
) -> SuccessResponse[TaskDetailResponse]:
    """Get detailed task information."""
    task = await service.get_task_detail(
        task_id=task_id,
        current_user=current_user,
    )
    return SuccessResponse(data=TaskDetailResponse.model_validate(task))


@router.patch(
    "/tasks/{task_id}",
    response_model=SuccessResponse[TaskResponse],
    status_code=status.HTTP_200_OK,
    summary="Cập nhật thông tin công việc",
    description=(
        "Cập nhật tiêu đề, mô tả, người phụ trách, mức độ ưu tiên, deadline của task. "
        "Chỉ dành cho OWNER hoặc ADMIN."
    ),
    operation_id="capNhatCongViec",
)
async def update_task(
    task_id: UUID,
    body: TaskUpdateRequest,
    current_user: User = Depends(get_current_user),
    service: TaskService = Depends(get_task_service),
) -> SuccessResponse[TaskResponse]:
    """Update an existing task."""
    task = await service.update_task(
        task_id=task_id,
        current_user=current_user,
        data=body,
    )
    return SuccessResponse(data=TaskResponse.model_validate(task))


@router.patch(
    "/tasks/{task_id}/status",
    response_model=SuccessResponse[TaskResponse],
    status_code=status.HTTP_200_OK,
    summary="Chuyển trạng thái công việc",
    description=(
        "Cho phép người phụ trách (assignee), EDITOR hoặc OWNER "
        "chuyển trạng thái công việc (TODO, IN_PROGRESS, IN_REVIEW, DONE)."
    ),
    operation_id="doiTrangThaiCongViec",
)
async def update_task_status(
    task_id: UUID,
    body: TaskStatusUpdateRequest,
    current_user: User = Depends(get_current_user),
    service: TaskService = Depends(get_task_service),
) -> SuccessResponse[TaskResponse]:
    """Update task status."""
    task = await service.update_task_status(
        task_id=task_id,
        status=body.status,
        current_user=current_user,
    )
    return SuccessResponse(data=TaskResponse.model_validate(task))


@router.patch(
    "/tasks/{task_id}/priority",
    response_model=SuccessResponse[TaskResponse],
    status_code=status.HTTP_200_OK,
    summary="Chuyển mức độ ưu tiên công việc",
    description=(
        "Cho phép người phụ trách (assignee), EDITOR, OWNER hoặc ADMIN "
        "chuyển mức độ ưu tiên công việc (LOW, MEDIUM, HIGH, URGENT)."
    ),
    operation_id="doiUuTienCongViec",
)
async def update_task_priority(
    task_id: UUID,
    body: TaskPriorityUpdateRequest,
    current_user: User = Depends(get_current_user),
    service: TaskService = Depends(get_task_service),
) -> SuccessResponse[TaskResponse]:
    """Update task priority."""
    task = await service.update_task_priority(
        task_id=task_id,
        priority=body.priority,
        current_user=current_user,
    )
    return SuccessResponse(data=TaskResponse.model_validate(task))


@router.delete(
    "/tasks/{task_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    operation_id="xoaCongViec",
    summary="Xóa công việc",
    description="Cho phép OWNER workspace hoặc system ADMIN xóa một công việc khỏi dự án.",
)
async def delete_task(
    task_id: UUID,
    current_user: User = Depends(get_current_user),
    service: TaskService = Depends(get_task_service),
) -> None:
    """Delete a task from project (OWNER or ADMIN only)."""
    await service.delete_task(task_id=task_id, current_user=current_user)
