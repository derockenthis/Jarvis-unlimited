from fastapi import APIRouter, Depends

from app.config import Settings
from app.dependencies import settings_dependency
from app.schemas import HealthResponse
from app.services.health_service import get_health

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
def health(settings: Settings = Depends(settings_dependency)) -> HealthResponse:
    return get_health(settings)
