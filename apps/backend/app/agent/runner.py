from collections.abc import AsyncIterator

from app.agent.agent import build_agent
from app.agent.event_translation import clean_assistant_text, translate_event
from app.agent.provider_config import ProviderRuntimeConfig
from app.agent.tools import (
    select_mcp_tools,
    build_vision_tools,
    build_workspace_tools,
)
from app.config import Settings
from app.schemas import ChatEvent, ChatRequest
from app.security.path_policy import PathPolicy
from app.services.conversation_context_service import ConversationContextService
from app.services.desktop_vision_service import DesktopVisionService
from app.services.memory_service import MemoryService
from app.services.mcp_service import McpService
from app.services.session_terminal_service import SessionTerminalService

APP_NAME = "jarvis-desktop"


class AgentStreamRunner:
    """Builds an ADK runner per request and translates its events for the UI."""

    def __init__(
        self,
        settings: Settings,
        policy: PathPolicy,
        mcp_service: McpService,
        terminal_service: SessionTerminalService,
        desktop_vision_service: DesktopVisionService,
        memory_service: MemoryService,
        conversation_context_service: ConversationContextService,
    ) -> None:
        self.settings = settings
        self.policy = policy
        self.mcp_service = mcp_service
        self.terminal_service = terminal_service
        self.desktop_vision_service = desktop_vision_service
        self.memory_service = memory_service
        self.conversation_context_service = conversation_context_service
        self._session_service: object | None = None

    def _debug(self, message: str) -> None:
        print(f"[jarvis-adk-runner] {message}", flush=True)

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
        request: ChatRequest,
    ) -> object:
        """Build an ADK Runner with tools bound to the current chat session."""

        from google.adk.apps.app import App, EventsCompactionConfig
        from google.adk.agents.context_cache_config import ContextCacheConfig
        from google.adk.runners import Runner

        session_service = self._ensure_session_service()
        provider_config = self._provider_config_from_request(request)
        conversation_context = self.conversation_context_service.render_session_context(
            request.session_id
        )
        self._debug(
            "build_runner "
            f"session_id={request.session_id} user_id={request.user_id} "
            f"provider={provider_config.provider} model={provider_config.model_name or '<default>'} "
            f"base_url={provider_config.base_url or '<default>'} "
            f"screen_share={request.screen_share_enabled} skills_root={request.skills_root or '<none>'}"
        )
        tools: list[object] = []
        if provider_config.supports_adk_tools:
            mcp_selection = await select_mcp_tools(
                self.mcp_service,
                provider_config,
                request.message,
                conversation_context,
            )
            mcp_tools = mcp_selection.tools
            self._debug(
                "resolved_mcp_tools "
                f"total={mcp_selection.total_resolved} "
                f"playwright_resolved={mcp_selection.playwright_resolved} "
                f"playwright_selected={mcp_selection.playwright_selected} "
                f"bundle={mcp_selection.playwright_bundle} "
                f"browser_intent={mcp_selection.browser_intent} "
                f"composite={mcp_selection.composite_tool_enabled}"
            )
            vision_tools = (
                build_vision_tools(self.desktop_vision_service, self.policy)
                if request.screen_share_enabled
                else []
            )
            workspace_tools = build_workspace_tools(self.policy)
            self._debug(f"resolved vision_tools={len(vision_tools)}")
            self._debug(f"resolved workspace_tools={len(workspace_tools)}")
            tools = [
                *workspace_tools,
                *vision_tools,
                *mcp_tools,
            ]
        self._debug(f"agent_tools={len(tools)}")
        agent = build_agent(
            self.settings,
            tools=tools,
            skills_root=request.skills_root,
            conversation_context=conversation_context,
            provider_config=provider_config,
        )
        self._debug(f"agent_built model={provider_config.litellm_model(self.settings)}")
        app = App(
            name=APP_NAME,
            root_agent=agent,
            events_compaction_config=EventsCompactionConfig(
                compaction_interval=max(1, self.settings.conversation_compaction_interval),
                overlap_size=max(0, self.settings.conversation_compaction_overlap),
            ),
            context_cache_config=self._context_cache_config(provider_config),
        )
        runner = Runner(app=app, session_service=session_service)
        self._debug("runner_ready")
        return runner

    def _context_cache_config(self, provider_config: ProviderRuntimeConfig) -> object | None:
        model_name = (provider_config.model_name or "").lower()
        if provider_config.provider == "ollama":
            return None
        if "gemini" not in model_name:
            return None

        from google.adk.agents.context_cache_config import ContextCacheConfig

        return ContextCacheConfig(
            min_tokens=self.settings.context_cache_min_tokens,
            ttl_seconds=self.settings.context_cache_ttl_seconds,
            cache_intervals=self.settings.context_cache_intervals,
        )

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

    def _provider_config_from_request(self, request: ChatRequest) -> ProviderRuntimeConfig:
        return ProviderRuntimeConfig(
            provider=request.provider or "openrouter",
            model_name=request.model,
            api_key=request.api_key,
            base_url=request.base_url,
        )

    def _provider_supports_adk_tools(self, provider: str | None) -> bool:
        return ProviderRuntimeConfig(provider=provider or "openrouter").supports_adk_tools

    def _missing_provider_configuration(self, request: ChatRequest) -> str | None:
        return self._provider_config_from_request(request).missing_configuration(self.settings)

    def _fallback_thought_events(
        self,
        translated_events: list[ChatEvent],
        function_calls: list[object],
        function_responses: list[object],
        assistant_started: bool,
    ) -> list[ChatEvent]:
        if any(chat_event.type == "thought" for chat_event in translated_events):
            return []

        if function_calls:
            tool_names = ", ".join(getattr(call, "name", "tool") for call in function_calls[:2])
            return [
                ChatEvent(
                    type="thought",
                    content=f"Planning next action with {tool_names}.",
                )
            ]

        if function_responses:
            tool_names = ", ".join(
                getattr(response, "name", "tool") for response in function_responses[:2]
            )
            return [
                ChatEvent(
                    type="thought",
                    content=f"Reviewing result from {tool_names}.",
                )
            ]

        if not assistant_started and any(
            chat_event.type == "assistant_message" for chat_event in translated_events
        ):
            return [ChatEvent(type="thought", content="Composing the response.")]

        return []

    async def stream_chat(self, request: ChatRequest) -> AsyncIterator[ChatEvent]:
        self._debug(
            "stream_chat_start "
            f"session_id={request.session_id} user_id={request.user_id} "
            f"provider={request.provider or 'openrouter'} model={request.model or '<default>'} "
            f"base_url={request.base_url or '<default>'}"
        )
        missing_configuration = self._missing_provider_configuration(request)
        if missing_configuration:
            self._debug(f"missing_configuration={missing_configuration}")
            yield ChatEvent(type="error", content=missing_configuration)
            yield ChatEvent(type="done", content="Chat stream completed.")
            return

        genai_types = None
        try:
            from google.genai import types

            genai_types = types

            await self.memory_service.append_observation(
                request.session_id, f"user[{request.user_id}]: {request.message}"
            )
            self._debug(f"user_observation_appended session_id={request.session_id}")
            async for chat_event in self._run_adk_chat(request, genai_types):
                self._debug(
                    f"yield_chat_event type={chat_event.type} "
                    f"content={chat_event.content[:200]!r}"
                )
                yield chat_event
        except Exception as exc:  # noqa: BLE001 - surfaced to the UI as a structured error event
            self._debug(f"stream_chat_exception type={type(exc).__name__} message={exc}")
            if (
                genai_types is not None
                and self._is_recoverable_session_error(exc)
                and self._session_service is not None
            ):
                try:
                    self._debug("recoverable_session_error_detected resetting_session")
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
                    self._debug(
                        f"retry_failed type={type(retry_exc).__name__} message={retry_exc}"
                    )
                    yield ChatEvent(type="error", content=f"Agent run failed: {retry_exc}")
                    yield ChatEvent(type="done", content="Chat stream completed.")
                    return
            yield ChatEvent(type="error", content=f"Agent run failed: {exc}")

        yield ChatEvent(type="done", content="Chat stream completed.")

    async def _run_adk_chat(self, request: ChatRequest, types: object) -> AsyncIterator[ChatEvent]:
        runner = await self._build_runner(request)
        await self._ensure_session(request.user_id, request.session_id)
        assistant_chunks: list[str] = []

        new_message = types.Content(role="user", parts=[types.Part.from_text(text=request.message)])

        self._debug("runner_loop_start")
        async for event in runner.run_async(
            user_id=request.user_id,
            session_id=request.session_id,
            new_message=new_message,
        ):
            event_class = event.__class__.__name__
            event_module = event.__class__.__module__
            function_calls = event.get_function_calls()
            function_responses = event.get_function_responses()
            content = getattr(event, "content", None)
            part_summary = []
            if content is not None and getattr(content, "parts", None):
                for part in content.parts:
                    part_summary.append(
                        {
                            "text": (getattr(part, "text", None) or "")[:120],
                            "thought": bool(getattr(part, "thought", False)),
                        }
                    )
            self._debug(
                "raw_event "
                f"class={event_module}.{event_class} "
                f"calls={[call.name for call in function_calls]} "
                f"responses={[response.name for response in function_responses]} "
                f"parts={part_summary}"
            )
            self._debug(
                "raw_event_fields "
                f"has_content={content is not None} "
                f"has_error={getattr(event, 'error_message', None) is not None} "
                f"has_actions={getattr(event, 'actions', None) is not None} "
                f"has_metadata={getattr(event, 'metadata', None) is not None} "
                f"repr={event!r}"
            )
            translated_events = translate_event(event)
            fallback_thoughts = self._fallback_thought_events(
                translated_events,
                function_calls,
                function_responses,
                assistant_started=bool(assistant_chunks),
            )
            output_events = [*fallback_thoughts, *translated_events]
            self._debug(
                "translated_event_types="
                f"{[chat_event.type for chat_event in output_events]}"
            )
            for chat_event in output_events:
                if chat_event.type == "assistant_message":
                    assistant_chunks.append(chat_event.content)
                    self._debug(
                        f"assistant_chunk_appended length={len(chat_event.content)} "
                        f"total={len(''.join(assistant_chunks))}"
                    )
                yield chat_event
        if assistant_chunks:
            self._debug(
                f"assistant_observation_appended session_id={request.session_id} "
                f"length={len(''.join(assistant_chunks))}"
            )
            await self.memory_service.append_observation(
                request.session_id, f"assistant[{request.user_id}]: {''.join(assistant_chunks)}"
            )
        else:
            self._debug("assistant_chunks_empty_no_observation_appended")

        current_event_count = self.memory_service.session_event_count(request.session_id)
        if current_event_count <= 0:
            self._debug(
                f"memory_promotion_skipped session_id={request.session_id} reason=no_events"
            )
            return
        event_delta = self.memory_service.event_delta_since_last_promotion(
            request.session_id,
            current_event_count,
        )
        if not self.memory_service.should_run_promotion_for_event_count(
            request.session_id, current_event_count
        ):
            self._debug(
                "memory_promotion_skipped "
                f"session_id={request.session_id} reason=before_compaction_interval "
                f"events={current_event_count} new_events={event_delta} "
                f"interval={max(1, self.settings.memory_promotion_interval)}"
            )
            return

        try:
            yield ChatEvent(
                type="thought",
                content=(
                    "Dream agent starting memory promotion using "
                    f"{self.settings.memory_dreamer_model} for session {request.session_id}."
                ),
            )
            promotion_result = await self.memory_service.promote_session_observations(
                request.session_id,
                event_count=current_event_count,
            )
            self._debug(
                "memory_promotion "
                f"session_id={request.session_id} "
                f"promoted={len(promotion_result['data']['promoted_node_ids'])} "
                f"consolidated={promotion_result['data']['consolidated']} "
                f"rejected={len(promotion_result['data']['rejected'])}"
            )
            yield ChatEvent(
                type="thought",
                content=(
                    "Dream agent finished memory promotion with "
                    f"{len(promotion_result['data']['promoted_node_ids'])} promoted nodes "
                    f"and {promotion_result['data']['consolidated']} consolidated observations."
                ),
            )
        except Exception as exc:  # noqa: BLE001 - memory promotion should not fail chat delivery
            self._debug(
                f"memory_promotion_exception type={type(exc).__name__} message={exc}"
            )
            yield ChatEvent(
                type="thought",
                content=f"Dream agent memory promotion failed: {type(exc).__name__}.",
            )

    def _is_recoverable_session_error(self, exc: Exception) -> bool:
        message = str(exc)
        return "Missing tool results for tool_call_id" in message or (
            "Tool '" in message and "not found" in message
        )

    def _translate_event(self, event: object) -> list[ChatEvent]:
        return translate_event(event)

    def _clean_assistant_text(self, text: str) -> str:
        return clean_assistant_text(text)

    async def _completed_turn_count(
        self, user_id: str, session_id: str
    ) -> int | None:
        if self._session_service is None:
            return None

        session = await self._session_service.get_session(
            app_name=APP_NAME, user_id=user_id, session_id=session_id
        )
        if session is None:
            return None

        invocation_ids: set[str] = set()
        for event in session.events:
            invocation_id = getattr(event, "invocation_id", None)
            if not invocation_id:
                continue
            invocation_ids.add(str(invocation_id))
        return len(invocation_ids)