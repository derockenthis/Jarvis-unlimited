from collections.abc import AsyncIterator
import json
import re

from app.agent.root_agent import build_root_agent
from app.config import Settings
from app.schemas import ChatEvent, ChatEventPayload, ChatRequest
from app.security.path_policy import PathPolicy
from app.services.desktop_vision_service import DesktopVisionService
from app.services.memory_service import MemoryService
from app.services.mcp_service import McpService
from app.services.session_terminal_service import SessionTerminalService
from app.tools.agent_tools import build_agent_tools
from app.tools.memory_tools import build_memory_tools
from app.tools.terminal_tools import build_terminal_tools
from app.tools.vision_tools import build_vision_tools

APP_NAME = "jarvis-desktop"
CHANNEL_MARKER_PATTERN = re.compile(r"<\|?/?channel\|?>\s*thought\s*", re.IGNORECASE)


class ChatRuntime:
    """FastAPI-facing adapter that drives the real ADK Runner and streams its events."""

    def __init__(
        self,
        settings: Settings,
        policy: PathPolicy,
        mcp_service: McpService,
        terminal_service: SessionTerminalService,
        desktop_vision_service: DesktopVisionService,
        memory_service: MemoryService,
    ) -> None:
        self.settings = settings
        self.policy = policy
        self.mcp_service = mcp_service
        self.terminal_service = terminal_service
        self.desktop_vision_service = desktop_vision_service
        self.memory_service = memory_service
        self._session_service: object | None = None

    def _ensure_session_service(self) -> object:
        """Lazily build the ADK session service so health checks work without ADK."""

        if self._session_service is not None:
            return self._session_service

        from google.adk.sessions.sqlite_session_service import SqliteSessionService

        self.settings.sqlite_path.parent.mkdir(parents=True, exist_ok=True)
        session_service = SqliteSessionService(str(self.settings.sqlite_path))
        self._session_service = session_service
        return session_service

    async def _build_runner(
        self,
        user_id: str,
        session_id: str,
        screen_share_enabled: bool,
        skills_root: str | None,
    ) -> object:
        """Build an ADK Runner with tools bound to the current chat session."""

        from google.adk.runners import Runner

        session_service = self._ensure_session_service()
        mcp_tools = await self.mcp_service.resolve_running_tools()
        vision_tools = (
            build_vision_tools(self.desktop_vision_service, self.policy)
            if screen_share_enabled
            else []
        )
        tools = [
            *build_agent_tools(self.policy),
            *build_terminal_tools(self.terminal_service, self.policy, user_id, session_id),
            *build_memory_tools(self.memory_service),
            *vision_tools,
            *mcp_tools,
        ]
        agent = build_root_agent(self.settings, tools=tools, skills_root=skills_root)
        runner = Runner(
            agent=agent,
            app_name=APP_NAME,
            session_service=session_service,
        )
        return runner

    async def _ensure_session(self, user_id: str, session_id: str) -> None:
        assert self._session_service is not None
        existing = await self._session_service.get_session(
            app_name=APP_NAME, user_id=user_id, session_id=session_id
        )
        if existing is None:
            await self._session_service.create_session(
                app_name=APP_NAME, user_id=user_id, session_id=session_id
            )

    async def _reset_session(self, user_id: str, session_id: str) -> None:
        assert self._session_service is not None
        await self._session_service.delete_session(
            app_name=APP_NAME, user_id=user_id, session_id=session_id
        )
        await self._session_service.create_session(
            app_name=APP_NAME, user_id=user_id, session_id=session_id
        )

    async def stream_chat(self, request: ChatRequest) -> AsyncIterator[ChatEvent]:
        if not self.settings.openrouter_api_key:
            yield ChatEvent(
                type="error",
                content=(
                    "OpenRouter is not configured. Set OPENROUTER_API_KEY to enable live ADK "
                    "model calls."
                ),
            )
            yield ChatEvent(type="done", content="Chat stream completed.")
            return

        genai_types = None
        try:
            from google.genai import types
            genai_types = types

            await self.memory_service.append_observation(
                request.session_id, f"user[{request.user_id}]: {request.message}"
            )
            async for chat_event in self._run_adk_chat(request, genai_types):
                yield chat_event
        except Exception as exc:  # noqa: BLE001 - surfaced to the UI as a structured error event
            if (
                genai_types is not None
                and self._is_recoverable_session_error(exc)
                and self._session_service is not None
            ):
                try:
                    await self._reset_session(request.user_id, request.session_id)
                    yield ChatEvent(
                        type="thought",
                        content="Resetting stale session tool history and retrying the request.",
                    )
                    async for chat_event in self._run_adk_chat(request, genai_types):
                        yield chat_event
                    yield ChatEvent(type="done", content="Chat stream completed.")
                    return
                except Exception as retry_exc:  # noqa: BLE001
                    yield ChatEvent(type="error", content=f"Agent run failed: {retry_exc}")
                    yield ChatEvent(type="done", content="Chat stream completed.")
                    return
            yield ChatEvent(type="error", content=f"Agent run failed: {exc}")

        yield ChatEvent(type="done", content="Chat stream completed.")

    async def _run_adk_chat(self, request: ChatRequest, types: object) -> AsyncIterator[ChatEvent]:
        runner = await self._build_runner(
            request.user_id,
            request.session_id,
            request.screen_share_enabled,
            request.skills_root,
        )
        await self._ensure_session(request.user_id, request.session_id)
        assistant_chunks: list[str] = []

        new_message = types.Content(role="user", parts=[types.Part.from_text(text=request.message)])

        async for event in runner.run_async(
            user_id=request.user_id,
            session_id=request.session_id,
            new_message=new_message,
        ):
            for chat_event in self._translate_event(event):
                if chat_event.type == "assistant_message":
                    assistant_chunks.append(chat_event.content)
                yield chat_event
        if assistant_chunks:
            await self.memory_service.append_observation(
                request.session_id, f"assistant[{request.user_id}]: {''.join(assistant_chunks)}"
            )

    def _is_recoverable_session_error(self, exc: Exception) -> bool:
        message = str(exc)
        return "Missing tool results for tool_call_id" in message or (
            "Tool '" in message and "not found" in message
        )

    def _translate_event(self, event: object) -> list[ChatEvent]:
        """Translate a single ADK event into zero or more UI chat events."""

        events: list[ChatEvent] = []

        for call in event.get_function_calls():
            args_detail = ""
            if call.args:
                try:
                    args_detail = json.dumps(call.args, default=str)
                except (TypeError, ValueError):
                    args_detail = str(call.args)
            events.append(
                ChatEvent(
                    type="tool_call",
                    content=f"Calling {call.name}",
                    payload=ChatEventPayload(
                        tool_name=call.name, status="running", detail=args_detail or None
                    ),
                )
            )

        for response in event.get_function_responses():
            status = "success"
            detail = None
            result = response.response
            if isinstance(result, dict):
                status = str(result.get("status", "error" if result.get("isError") else "success"))
                detail = result.get("error") or result.get("diff")
                if detail is None and isinstance(result.get("content"), list):
                    text_parts = [
                        item.get("text", "")
                        for item in result["content"]
                        if isinstance(item, dict) and item.get("type") == "text"
                    ]
                    detail = "\n".join(part for part in text_parts if part) or None
                if detail is None and "data" in result:
                    try:
                        detail = json.dumps(result["data"], default=str)[:2000]
                    except (TypeError, ValueError):
                        detail = str(result["data"])[:2000]
            events.append(
                ChatEvent(
                    type="tool_result",
                    content=f"{response.name} finished",
                    payload=ChatEventPayload(
                        tool_name=response.name, status=status, detail=detail
                    ),
                )
            )

        content = getattr(event, "content", None)
        if content is not None and content.parts:
            for part in content.parts:
                text = getattr(part, "text", None)
                if not text:
                    continue
                if getattr(part, "thought", False):
                    events.append(ChatEvent(type="thought", content=text))
                else:
                    cleaned_text = self._clean_assistant_text(text)
                    if cleaned_text:
                        events.append(ChatEvent(type="assistant_message", content=cleaned_text))

        return events

    def _clean_assistant_text(self, text: str) -> str:
        """Remove provider channel markers that should not render as final answer text."""

        return CHANNEL_MARKER_PATTERN.sub("", text)
