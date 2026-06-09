from collections.abc import AsyncIterator
import json

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from app.dependencies import get_chat_service
from app.schemas import ChatRequest
from app.services.chat_service import ChatService

router = APIRouter(prefix="/api", tags=["chat"])


@router.post("/chat")
async def chat(
    request: ChatRequest,
    service: ChatService = Depends(get_chat_service),
) -> StreamingResponse:
    async def event_stream() -> AsyncIterator[str]:
        async for event in service.stream_chat(request):
            yield f"data: {json.dumps(event.model_dump())}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")
