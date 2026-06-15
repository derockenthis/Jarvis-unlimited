from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import Response

from app.dependencies import get_speech_to_text_service, get_text_to_speech_service
from app.schemas import SpeechSynthesisRequest, SpeechTranscriptionResponse
from app.services.text_to_speech_service import TextToSpeechService
from app.services.transcription_service import SpeechToTextService

router = APIRouter(prefix="/api", tags=["speech"])


@router.post("/speech/transcribe", response_model=SpeechTranscriptionResponse)
async def transcribe_speech(
    audio: UploadFile = File(...),
    model: str = Form(default=""),
    service: SpeechToTextService = Depends(get_speech_to_text_service),
) -> SpeechTranscriptionResponse:
    result = service.transcribe_audio(
        await audio.read(),
        audio.filename or "speech.webm",
        audio.content_type,
        model=model or None,
    )

    if result["status"] != "success":
        error_message = str(result.get("error") or "Speech transcription failed.")
        status_code = 503 if "not configured" in error_message.lower() else 502
        raise HTTPException(status_code=status_code, detail=error_message)

    return SpeechTranscriptionResponse.model_validate(result["data"])


@router.post("/speech/synthesize")
async def synthesize_speech(
    request: SpeechSynthesisRequest,
    service: TextToSpeechService = Depends(get_text_to_speech_service),
) -> Response:
    result = service.synthesize_speech(request.text)

    if result["status"] != "success":
        error_message = str(result.get("error") or "Speech synthesis failed.")
        status_code = 503 if "not installed" in error_message.lower() else 502
        raise HTTPException(status_code=status_code, detail=error_message)

    data = result["data"]
    return Response(
        content=data["audio_bytes"],
        media_type=str(data.get("content_type") or "audio/wav"),
        headers={
            "X-TTS-Provider": str(data.get("provider") or ""),
            "X-TTS-Voice": str(data.get("voice") or ""),
        },
    )
