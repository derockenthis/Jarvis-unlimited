from collections.abc import AsyncIterator

from app.runtime.adk_runner import ChatRuntime
from app.schemas import ChatEvent, ChatRequest


class ChatService:
    def __init__(self, runtime: ChatRuntime) -> None:
        self.runtime = runtime

    async def stream_chat(self, request: ChatRequest) -> AsyncIterator[ChatEvent]:
        async for event in self.runtime.stream_chat(request):
            yield event
