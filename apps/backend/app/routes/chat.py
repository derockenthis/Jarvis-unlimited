from collections.abc import AsyncIterator
import json
import httpx

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse, JSONResponse

from app.dependencies import get_chat_service
from app.schemas import ChatRequest
from app.services.chat_service import ChatService

router = APIRouter(prefix="/api", tags=["chat"])

@router.get("/models/ollama")
async def get_ollama_models(base_url: str = "http://localhost:11434"):
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{base_url.rstrip('/')}/api/tags", timeout=2.0)
            response.raise_for_status()
            data = response.json()
            models = [m["name"] for m in data.get("models", [])]
            return JSONResponse({"models": models})
    except Exception as e:
        return JSONResponse({"error": str(e), "models": []})

@router.post("/chat")
async def chat(
    request: ChatRequest,
    service: ChatService = Depends(get_chat_service),
) -> StreamingResponse:
    async def event_stream() -> AsyncIterator[str]:
        async for event in service.stream_chat(request):
            yield f"data: {json.dumps(event.model_dump())}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")
