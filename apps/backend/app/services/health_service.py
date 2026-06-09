import shutil

from app.config import Settings
from app.schemas import HealthResponse


def get_health(settings: Settings) -> HealthResponse:
    return HealthResponse(
        status="ok",
        app="jarvis-agent-backend",
        openrouter_configured=bool(settings.openrouter_api_key),
        ripgrep_available=shutil.which("rg") is not None,
    )
