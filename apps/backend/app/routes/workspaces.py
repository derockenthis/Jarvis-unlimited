from fastapi import APIRouter, Depends

from app.config import Settings
from app.dependencies import settings_dependency
from app.schemas import WorkspaceRoot
from app.services.workspace_service import get_workspace_roots

router = APIRouter(prefix="/api", tags=["workspaces"])


@router.get("/workspaces")
def workspace_roots(settings: Settings = Depends(settings_dependency)) -> dict[str, list[WorkspaceRoot]]:
    return {"roots": get_workspace_roots(settings)}
