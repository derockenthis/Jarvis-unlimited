from pathlib import Path

from app.config import Settings
from app.schemas import WorkspaceRoot


def get_workspace_roots(settings: Settings) -> list[WorkspaceRoot]:
    if settings.full_filesystem_access:
        return [WorkspaceRoot(path=str(Path("/").resolve()), access="full")]
    return [WorkspaceRoot(path=str(path), access="granted") for path in settings.allowed_root_paths]
