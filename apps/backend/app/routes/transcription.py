from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from app.dependencies import get_speech_to_text_service
from app.schemas import SpeechTranscriptionResponse
from app.services.transcription_service import SpeechToTextService

router = APIRouter(prefix="/api", tags=["speech"])


@router.post("/speech/transcribe", response_model=SpeechTranscriptionResponse)
async def transcribe_speech(
    audio: UploadFile = File(...),
    service: SpeechToTextService = Depends(get_speech_to_text_service),
) -> SpeechTranscriptionResponse:
    result = service.transcribe_audio(
        await audio.read(),
        audio.filename or "speech.webm",
        audio.content_type,
    )

    if result["status"] != "success":
        error_message = str(result.get("error") or "Speech transcription failed.")
        status_code = 503 if "not configured" in error_message.lower() else 502
        raise HTTPException(status_code=status_code, detail=error_message)

    return SpeechTranscriptionResponse.model_validate(result["data"])