from fastapi import APIRouter

from app.api.v1.auth import router as auth_router
from app.api.v1.labels import router as labels_router
from app.api.v1.labels import task_label_router
from app.api.v1.projects import router as projects_router
from app.api.v1.tasks import router as tasks_router
from app.api.v1.users import router as users_router
from app.api.v1.workspaces import router as workspaces_router

router = APIRouter()

router.include_router(auth_router, prefix="/auth", tags=["Auth"])
router.include_router(users_router, prefix="/users", tags=["Users"])
router.include_router(workspaces_router, prefix="/workspaces", tags=["Workspaces"])
router.include_router(projects_router, prefix="/projects", tags=["Projects"])
router.include_router(labels_router)
router.include_router(task_label_router)
router.include_router(tasks_router, tags=["Tasks"])
