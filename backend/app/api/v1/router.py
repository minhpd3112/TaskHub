from fastapi import APIRouter

from app.api.v1.auth import router as auth_router
from app.api.v1.projects import router as projects_router
from app.api.v1.users import router as users_router
from app.api.v1.workspaces import router as workspaces_router

router = APIRouter()

router.include_router(auth_router, prefix="/auth", tags=["Auth"])
router.include_router(users_router, prefix="/users", tags=["Users"])
router.include_router(workspaces_router, prefix="/workspaces", tags=["Workspaces"])
router.include_router(projects_router, prefix="/projects", tags=["Projects"])
