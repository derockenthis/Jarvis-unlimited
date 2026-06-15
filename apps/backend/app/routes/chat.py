from collections.abc import AsyncIterator
import json
import httpx

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse, JSONResponse

from app.dependencies import get_chat_service
from app.schemas import ChatRequest, Conversation, ConversationMessage
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


@router.post("/chat/{session_id}/cancel")
async def cancel_chat(
    session_id: str,
    service: ChatService = Depends(get_chat_service),
) -> JSONResponse:
    cancelled = await service.cancel_chat(session_id)
    return JSONResponse(
        {"status": "success", "session_id": session_id, "cancelled": cancelled}
    )


@router.get("/conversations", response_model=list[Conversation])
async def list_conversations(
    user_id: str = "local-user",
    limit: int = Query(default=50, ge=1, le=200),
    service: ChatService = Depends(get_chat_service),
) -> list[Conversation]:
    return await service.list_conversations(user_id=user_id, limit=limit)


@router.get("/conversations/{conversation_id}", response_model=Conversation)
async def get_conversation(
    conversation_id: str,
    service: ChatService = Depends(get_chat_service),
) -> Conversation:
    conversation = await service.get_conversation(conversation_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return conversation


@router.get("/conversations/{conversation_id}/messages", response_model=list[ConversationMessage])
async def get_conversation_messages(
    conversation_id: str,
    service: ChatService = Depends(get_chat_service),
) -> list[ConversationMessage]:
    return await service.get_conversation_messages(conversation_id)


@router.delete("/conversations/{conversation_id}")
async def delete_conversation(
    conversation_id: str,
    user_id: str = "local-user",
    service: ChatService = Depends(get_chat_service),
) -> JSONResponse:
    deleted = await service.delete_conversation(conversation_id, user_id=user_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return JSONResponse({"status": "success", "message": "Conversation deleted"})
