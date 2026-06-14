from fastapi import APIRouter, Depends

from app.dependencies import get_settings_service
from app.schemas import ModelSettingsResponse, UpsertModelSettingsRequest
from app.services.settings_service import SettingsService

router = APIRouter(prefix="/api/settings", tags=["settings"])


@router.get("/model", response_model=ModelSettingsResponse)
def get_model_settings(service: SettingsService = Depends(get_settings_service)) -> ModelSettingsResponse:
    return service.get_model_settings()


@router.put("/model", response_model=ModelSettingsResponse)
def put_model_settings(
    request: UpsertModelSettingsRequest,
    service: SettingsService = Depends(get_settings_service),
) -> ModelSettingsResponse:
    return service.save_model_settings(request)