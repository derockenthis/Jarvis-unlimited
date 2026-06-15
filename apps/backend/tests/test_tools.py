import os
import sys
from types import ModuleType
from types import SimpleNamespace
from pathlib import Path
import json
import sqlite3
import subprocess

import pytest

from app.agent.runner import AgentStreamRunner
from app.agent.tools.cli import CLIAgentTool
from app.config import Settings
from app.mcp.adk_toolset import build_running_mcp_toolsets, resolve_running_mcp_tools
from app.mcp.presets import PLAYWRIGHT_MCP_ISOLATED_PRESET
from app.schemas import ChatEvent, ChatRequest, McpActionRequest, McpToolConfig
from app.security.command_policy import CommandPolicy
from app.security.path_policy import PathPolicy
from app.services.conversation_context_service import ConversationContextService
from app.services.desktop_vision_service import DesktopVisionService
from app.services.memory_service import MemoryService
from app.services.mcp_service import McpService
from app.services.session_terminal_service import SessionTerminalService
from app.services.transcription_service import SpeechToTextService
from app.tools.agent_tools import build_agent_tools
from app.tools.search_tools import read_file_section, ripgrep_search


def test_read_file_section_returns_requested_lines(tmp_path: Path) -> None:
    file_path = tmp_path / "sample.txt"
    file_path.write_text("one\ntwo\nthree\n", encoding="utf-8")
    policy = PathPolicy([tmp_path])

    result = read_file_section(str(file_path), 2, 3, policy)

    assert result.status == "success"
    assert result.data["content"] == "two\nthree"


def test_ripgrep_missing_dependency_is_structured(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr("app.tools.search_tools.shutil.which", lambda _: None)
    policy = PathPolicy([tmp_path])

    result = ripgrep_search("needle", str(tmp_path), 10, policy)

    assert result.status == "error"
    assert "ripgrep is not installed" in (result.error or "")


def test_build_agent_tools_includes_cli_sub_agent_tool(tmp_path: Path) -> None:
    policy = PathPolicy([tmp_path])

    tools = build_agent_tools(policy)

    assert any(getattr(tool, "__name__", "") == "spawn_sub_agent" for tool in tools)


def test_cli_agent_tool_rejects_unsupported_tool(tmp_path: Path) -> None:
    policy = PathPolicy([tmp_path])
    tool = CLIAgentTool(policy)

    result = tool.spawn_sub_agent(
        name="code_reviewer",
        description="Reviews code",
        instructions="Review this code",
        tools=["filesystem", "browser"],
    )

    assert result["status"] == "error"
    assert "Unsupported sub-agent tools" in (result["error"] or "")


def test_cli_agent_tool_runs_whitelisted_sub_agent(
    monkeypatch, tmp_path: Path
) -> None:
    policy = PathPolicy([tmp_path])
    tool = CLIAgentTool(policy)

    captured: dict[str, object] = {}

    def _fake_run(
        argv, check, capture_output, text, cwd, env, timeout, preexec_fn
    ) -> subprocess.CompletedProcess[str]:
        captured.update(
            {
                "argv": argv,
                "check": check,
                "capture_output": capture_output,
                "text": text,
                "cwd": cwd,
                "env": env,
                "timeout": timeout,
                "preexec_fn": preexec_fn,
            }
        )
        spec_file = Path(argv[4])
        spec = json.loads(spec_file.read_text(encoding="utf-8"))
        captured["spec"] = spec
        return subprocess.CompletedProcess(argv, 0, stdout="sub-agent output\n", stderr="")

    monkeypatch.setattr("app.agent.tools.cli.subprocess.run", _fake_run)

    result = tool.spawn_sub_agent(
        name="code_reviewer",
        description="A specialized agent that reviews code.",
        instructions="Review the provided code snippets for vulnerabilities.",
        tools=["filesystem", "terminal"],
        timeout_seconds=5,
    )

    assert result["status"] == "success"
    assert result["data"]["command"] == [
        sys.executable,
        "-m",
        "app.agent.sub_agent_launcher",
        "--spec-file",
        captured["argv"][4],
    ]
    assert result["data"]["name"] == "code_reviewer"
    assert captured["spec"] == {
        "name": "code_reviewer",
        "description": "A specialized agent that reviews code.",
        "instructions": "Review the provided code snippets for vulnerabilities.",
        "tools": ["filesystem", "terminal"],
    }
    assert result["data"]["stdout"] == "sub-agent output\n"
    assert captured["timeout"] == 5
    assert captured["env"]["PYTHONUNBUFFERED"] == "1"
    assert captured["env"]["PATH"]
    assert Path(captured["env"]["PYTHONPATH"].split(os.pathsep)[0]) == Path(
        "/Users/derekin/Desktop/Jarvis-unlimited/apps/backend"
    )
    assert captured["cwd"] == tmp_path
    assert callable(captured["preexec_fn"])


def test_cli_agent_tool_accepts_browser_tools(monkeypatch, tmp_path: Path) -> None:
    policy = PathPolicy([tmp_path])
    tool = CLIAgentTool(policy)

    def _fake_run(
        argv, check, capture_output, text, cwd, env, timeout, preexec_fn
    ) -> subprocess.CompletedProcess[str]:
        spec_file = Path(argv[4])
        spec = json.loads(spec_file.read_text(encoding="utf-8"))
        assert spec["tools"] == ["filesystem", "browser_navigate", "browser_snapshot"]
        return subprocess.CompletedProcess(argv, 0, stdout="ok\n", stderr="")

    monkeypatch.setattr("app.agent.tools.cli.subprocess.run", _fake_run)

    result = tool.spawn_sub_agent(
        name="browser_worker",
        description="Uses browser tools.",
        instructions="Inspect the page.",
        tools=["filesystem", "browser_navigate", "browser_snapshot"],
    )

    assert result["status"] == "success"
    assert result["data"]["tools"] == ["filesystem", "browser_navigate", "browser_snapshot"]


def test_runner_prunes_compacted_session_events(tmp_path: Path) -> None:
    sqlite_path = tmp_path / "jarvis.sqlite"
    settings = Settings(
        OPENROUTER_API_KEY="test-key",
        JARVIS_SQLITE_PATH=str(sqlite_path),
        JARVIS_MEMORY_ROOT=str(tmp_path / "memory"),
        JARVIS_CONVERSATION_COMPACTION_INTERVAL=3,
        JARVIS_CONVERSATION_COMPACTION_OVERLAP=2,
    )
    memory_service = MemoryService(settings)
    runtime = AgentStreamRunner(
        settings,
        PathPolicy([tmp_path], full_access=True),
        McpService(),
        SessionTerminalService(),
        DesktopVisionService(settings),
        memory_service,
        ConversationContextService(settings.sqlite_path),
    )

    with sqlite3.connect(sqlite_path) as database:
        database.execute(
            """
            CREATE TABLE events (
                id TEXT NOT NULL,
                app_name TEXT NOT NULL,
                user_id TEXT NOT NULL,
                session_id TEXT NOT NULL,
                invocation_id TEXT NOT NULL,
                timestamp REAL NOT NULL,
                event_data TEXT NOT NULL,
                PRIMARY KEY (app_name, user_id, session_id, id)
            )
            """
        )
        for index in range(5):
            database.execute(
                """
                INSERT INTO events (
                    id, app_name, user_id, session_id, invocation_id, timestamp, event_data
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    f"event-{index}",
                    "jarvis-desktop",
                    "local-user",
                    "session-1",
                    f"invocation-{index}",
                    float(index),
                    "{}",
                ),
            )
        database.execute(
            """
            INSERT INTO events (
                id, app_name, user_id, session_id, invocation_id, timestamp, event_data
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            ("other-event", "jarvis-desktop", "local-user", "session-2", "other", 100.0, "{}"),
        )
        database.commit()

    runtime._prune_compacted_session_events("local-user", "session-1", 5)

    with sqlite3.connect(sqlite_path) as database:
        retained = database.execute(
            """
            SELECT id FROM events
            WHERE app_name = ? AND user_id = ? AND session_id = ?
            ORDER BY timestamp
            """,
            ("jarvis-desktop", "local-user", "session-1"),
        ).fetchall()
        other_count = database.execute(
            "SELECT COUNT(*) FROM events WHERE session_id = ?",
            ("session-2",),
        ).fetchone()
        promotion_row = database.execute(
            """
            SELECT last_promotion_event_count
            FROM memory_promotion_state
            WHERE session_id = ?
            """,
            ("session-1",),
        ).fetchone()

    assert [row[0] for row in retained] == ["event-3", "event-4"]
    assert int(other_count[0]) == 1
    assert int(promotion_row[0]) == 2


def test_build_running_mcp_toolsets_filters_by_enabled_and_running(monkeypatch) -> None:
    configs = [
        McpToolConfig(
            id="playwright",
            name="Playwright",
            command="npx",
            args=["@playwright/mcp@latest"],
            enabled=True,
            status="running",
            description="",
        ),
        McpToolConfig(
            id="stopped",
            name="Stopped",
            command="npx",
            args=["tool"],
            enabled=True,
            status="stopped",
            description="",
        ),
        McpToolConfig(
            id="disabled",
            name="Disabled",
            command="npx",
            args=["tool"],
            enabled=False,
            status="running",
            description="",
        ),
    ]

    monkeypatch.setattr(
        "app.mcp.adk_toolset.build_mcp_toolset", lambda config: f"toolset:{config.id}"
    )

    result = build_running_mcp_toolsets(configs)

    assert result == ["toolset:playwright"]


def test_playwright_mcp_defaults_to_running_chrome_and_respects_manual_stop() -> None:
    service = McpService()

    tools = service.list_tools()

    assert tools[0].id == "playwright"
    assert tools[0].status == "running"
    assert tools[0].auto_start is True
    assert "--browser=chrome" in tools[0].args
    assert "--shared-browser-context" in tools[0].args
    assert "--isolated" not in tools[0].args
    assert not any(arg.startswith("--user-data-dir=") for arg in tools[0].args)

    service.stop_tool("playwright", McpActionRequest())
    restarted = service.ensure_auto_started_tools()[0]

    assert restarted.status == "stopped"


def test_isolated_playwright_preset_omits_shared_browser_context() -> None:
    assert "--shared-browser-context" not in PLAYWRIGHT_MCP_ISOLATED_PRESET.args


async def test_resolve_running_mcp_tools_flattens_toolset_tools(monkeypatch) -> None:
    class _FakeToolset:
        async def get_tools(self):
            return ["browser_navigate", "browser_snapshot"]

    monkeypatch.setattr("app.mcp.adk_toolset.build_mcp_toolset", lambda config: _FakeToolset())

    result = await resolve_running_mcp_tools(
        [
            McpToolConfig(
                id="playwright",
                name="Playwright",
                command="npx",
                args=["@playwright/mcp@latest"],
                enabled=True,
                status="running",
                description="",
            )
        ]
    )

    assert result == ["browser_navigate", "browser_snapshot"]


@pytest.mark.asyncio
async def test_sub_agent_launcher_resolves_requested_browser_tools(monkeypatch, tmp_path: Path) -> None:
    from app.agent import sub_agent_launcher

    class _FakeTool:
        def __init__(self, name: str) -> None:
            self.name = name

    class _FakeMcpService:
        async def resolve_running_tools(self):
            return [
                _FakeTool("browser_navigate"),
                _FakeTool("browser_snapshot"),
                _FakeTool("browser_click"),
            ]

    monkeypatch.setattr(
        sub_agent_launcher,
        "McpService",
        lambda **kwargs: _FakeMcpService(),
    )
    monkeypatch.setattr(
        sub_agent_launcher,
        "build_workspace_tools",
        lambda policy: ["filesystem-tool"],
    )

    policy = PathPolicy([tmp_path])
    tools = await sub_agent_launcher._build_sub_agent_tools(
        policy,
        ["filesystem", "browser_navigate", "browser_snapshot"],
        "code_reviewer",
    )

    assert tools[0] == "filesystem-tool"
    assert [tool.name for tool in tools[1:]] == ["browser_navigate", "browser_snapshot"]


async def test_mcp_service_reuses_toolset_between_calls_and_closes_on_stop(monkeypatch) -> None:
    closed_ids: list[str] = []
    created_ids: list[str] = []

    class _FakeToolset:
        def __init__(self, tool_id: str) -> None:
            self.tool_id = tool_id

        async def get_tools(self):
            return [f"tool:{self.tool_id}"]

        async def close(self):
            closed_ids.append(self.tool_id)

    def _build_toolset(config: McpToolConfig):
        created_ids.append(config.id)
        return _FakeToolset(config.id)

    monkeypatch.setattr("app.services.mcp_service.build_mcp_toolset", _build_toolset)

    service = McpService()

    first = await service.resolve_running_tools()
    second = await service.resolve_running_tools()

    assert first == ["tool:playwright"]
    assert second == ["tool:playwright"]
    assert created_ids == ["playwright"]

    service.stop_tool("playwright", McpActionRequest())
    stopped = await service.resolve_running_tools()

    assert stopped == []
    assert closed_ids == ["playwright"]


def test_session_terminal_service_persists_cwd_and_rejects_disallowed_commands(
    tmp_path: Path,
) -> None:
    policy = PathPolicy([tmp_path])
    service = SessionTerminalService(CommandPolicy())
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    nested = workspace / "nested"
    nested.mkdir()

    spawned = service.spawn(
        user_id="local-user",
        session_id="chat-1",
        cwd=str(workspace),
        path_policy=policy,
    )

    assert spawned["status"] == "success"
    terminal_id = spawned["data"]["terminal_id"]

    pwd_result = service.run(
        user_id="local-user",
        session_id="chat-1",
        terminal_id=terminal_id,
        command="pwd",
        path_policy=policy,
    )
    assert pwd_result["status"] == "success"
    assert pwd_result["data"]["cwd"] == str(workspace)
    assert str(workspace) in pwd_result["data"]["stdout"]

    cd_result = service.run(
        user_id="local-user",
        session_id="chat-1",
        terminal_id=terminal_id,
        command="cd nested",
        path_policy=policy,
    )
    assert cd_result["status"] == "success"
    assert cd_result["data"]["cwd"] == str(nested)

    read_back = service.read(
        user_id="local-user",
        session_id="chat-1",
        terminal_id=terminal_id,
    )
    assert read_back["data"]["cwd"] == str(nested)

    blocked = service.run(
        user_id="local-user",
        session_id="chat-1",
        terminal_id=terminal_id,
        command="echo hello",
        path_policy=policy,
    )
    assert blocked["status"] == "error"
    assert "not allowed" in blocked["error"]


def test_desktop_vision_service_captures_screenshot(tmp_path: Path, monkeypatch) -> None:
    screenshot_dir = tmp_path / "screens"
    settings = Settings(
        OPENROUTER_API_KEY="test-key",
        JARVIS_SCREENSHOT_DIR=str(screenshot_dir),
    )
    service = DesktopVisionService(settings)

    def _fake_run(command, check, capture_output, text, timeout):
        target = Path(command[-1])
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(b"png-data")
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr("app.services.desktop_vision_service.subprocess.run", _fake_run)

    result = service.capture_desktop_screenshot("desktop-now")

    assert result["status"] == "success"
    assert Path(result["data"]["path"]).exists()


async def test_memory_service_logs_observations_and_reports_status(tmp_path: Path) -> None:
    settings = Settings(
        OPENROUTER_API_KEY="test-key",
        JARVIS_MEMORY_ROOT=str(tmp_path / "memory"),
        JARVIS_SQLITE_PATH=str(tmp_path / "jarvis.sqlite"),
    )
    service = MemoryService(settings)

    await service.append_observation("session-1", "user: hello")
    await service.append_observation("session-1", "assistant: hi")

    status = service.status()

    assert status["status"] == "success"
    assert status["data"]["node_count"] == 0
    assert status["data"]["observation_count"] == 2
    assert status["data"]["dreamer_model"] == "google/gemini-3-flash-preview"


async def test_stream_chat_emits_visible_memory_promotion_thought_events(
    monkeypatch, tmp_path: Path
) -> None:
    settings = Settings(
        OPENROUTER_API_KEY="test-key",
        JARVIS_MEMORY_ROOT=str(tmp_path / "memory"),
        JARVIS_SQLITE_PATH=str(tmp_path / "jarvis.sqlite"),
    )
    runtime = AgentStreamRunner(
        settings,
        PathPolicy([tmp_path], full_access=True),
        McpService(),
        SessionTerminalService(),
        DesktopVisionService(settings),
        MemoryService(settings),
        ConversationContextService(settings.sqlite_path),
    )

    class _MemoryService:
        async def append_observation(self, session_id: str, observation: str) -> None:
            return None

        def session_event_count(self, session_id: str) -> int:
            return 5

        def event_delta_since_last_promotion(self, session_id: str, event_count: int) -> int:
            return 5

        def should_run_promotion_for_event_count(
            self, session_id: str, event_count: int
        ) -> bool:
            return True

        async def promote_session_observations(
            self, session_id: str, event_count: int
        ) -> dict[str, object]:
            return {
                "status": "success",
                "data": {
                    "promoted_node_ids": ["node-1"],
                    "consolidated": 2,
                    "rejected": [],
                },
            }

    class _FakeRunner:
        async def run_async(self, user_id: str, session_id: str, new_message: object):
            class _FakeEvent:
                def __init__(self) -> None:
                    self.content = _FakeContent(role="assistant", parts=[_FakePart("Assistant reply.")])

                def get_function_calls(self) -> list[object]:
                    return []

                def get_function_responses(self) -> list[object]:
                    return []

            yield _FakeEvent()

    async def _fake_build_runner(self, request: ChatRequest) -> object:
        return _FakeRunner()

    async def _fake_ensure_session(self, user_id: str, session_id: str) -> None:
        return None

    class _FakePart:
        def __init__(self, text: str) -> None:
            self.text = text

        @staticmethod
        def from_text(text: str) -> "_FakePart":
            return _FakePart(text)

    class _FakeContent:
        def __init__(self, role: str, parts: list[_FakePart]) -> None:
            self.role = role
            self.parts = parts

    fake_types = ModuleType("google.genai.types")
    fake_types.Content = _FakeContent
    fake_types.Part = _FakePart

    google_module = ModuleType("google")
    genai_module = ModuleType("google.genai")
    genai_module.types = fake_types
    google_module.genai = genai_module
    monkeypatch.setitem(sys.modules, "google", google_module)
    monkeypatch.setitem(sys.modules, "google.genai", genai_module)
    monkeypatch.setitem(sys.modules, "google.genai.types", fake_types)

    runtime.memory_service = _MemoryService()
    monkeypatch.setattr(AgentStreamRunner, "_build_runner", _fake_build_runner)
    monkeypatch.setattr(AgentStreamRunner, "_ensure_session", _fake_ensure_session)
    monkeypatch.setattr(
        "app.agent.runner.translate_event",
        lambda event: [ChatEvent(type="assistant_message", content="Assistant reply.")],
    )

    events = []
    async for event in runtime.stream_chat(ChatRequest(message="hello")):
        events.append(event)

    assert [event.type for event in events] == [
        "thought",
        "assistant_message",
        "thought",
        "thought",
        "done",
    ]
    assert events[0].content == "Composing the response."
    assert "Dream agent starting memory promotion" in events[2].content
    assert "Dream agent finished memory promotion" in events[3].content


async def test_stream_chat_emits_fallback_runtime_thoughts_for_tool_progress(
    monkeypatch, tmp_path: Path
) -> None:
    settings = Settings(
        OPENROUTER_API_KEY="test-key",
        JARVIS_MEMORY_ROOT=str(tmp_path / "memory"),
        JARVIS_SQLITE_PATH=str(tmp_path / "jarvis.sqlite"),
    )
    runtime = AgentStreamRunner(
        settings,
        PathPolicy([tmp_path], full_access=True),
        McpService(),
        SessionTerminalService(),
        DesktopVisionService(settings),
        MemoryService(settings),
        ConversationContextService(settings.sqlite_path),
    )

    class _MemoryService:
        async def append_observation(self, session_id: str, observation: str) -> None:
            return None

        def session_event_count(self, session_id: str) -> int:
            return 0

        def event_delta_since_last_promotion(self, session_id: str, event_count: int) -> int:
            return 0

        def should_run_promotion_for_event_count(
            self, session_id: str, event_count: int
        ) -> bool:
            return False

    class _FakeEvent:
        def __init__(self, kind: str) -> None:
            self.kind = kind
            self.content = None

        def get_function_calls(self) -> list[object]:
            if self.kind != "tool_call":
                return []

            class _Call:
                name = "list_directory_tool"

            return [_Call()]

        def get_function_responses(self) -> list[object]:
            if self.kind != "tool_result":
                return []

            class _Response:
                name = "list_directory_tool"

            return [_Response()]

    class _FakeRunner:
        async def run_async(self, user_id: str, session_id: str, new_message: object):
            yield _FakeEvent("tool_call")
            yield _FakeEvent("tool_result")
            yield _FakeEvent("assistant_message")

    async def _fake_build_runner(self, request: ChatRequest) -> object:
        return _FakeRunner()

    async def _fake_ensure_session(self, user_id: str, session_id: str) -> None:
        return None

    class _FakePart:
        def __init__(self, text: str) -> None:
            self.text = text

        @staticmethod
        def from_text(text: str) -> "_FakePart":
            return _FakePart(text)

    class _FakeContent:
        def __init__(self, role: str, parts: list[_FakePart]) -> None:
            self.role = role
            self.parts = parts

    fake_types = ModuleType("google.genai.types")
    fake_types.Content = _FakeContent
    fake_types.Part = _FakePart

    google_module = ModuleType("google")
    genai_module = ModuleType("google.genai")
    genai_module.types = fake_types
    google_module.genai = genai_module
    monkeypatch.setitem(sys.modules, "google", google_module)
    monkeypatch.setitem(sys.modules, "google.genai", genai_module)
    monkeypatch.setitem(sys.modules, "google.genai.types", fake_types)

    runtime.memory_service = _MemoryService()
    monkeypatch.setattr(AgentStreamRunner, "_build_runner", _fake_build_runner)
    monkeypatch.setattr(AgentStreamRunner, "_ensure_session", _fake_ensure_session)

    def _fake_translate_event(event: _FakeEvent) -> list[ChatEvent]:
      if event.kind == "tool_call":
          return [ChatEvent(type="tool_call", content="Calling list_directory_tool")]
      if event.kind == "tool_result":
          return [ChatEvent(type="tool_result", content="list_directory_tool finished")]
      return [ChatEvent(type="assistant_message", content="Assistant reply.")]

    monkeypatch.setattr("app.agent.runner.translate_event", _fake_translate_event)

    events = []
    async for event in runtime.stream_chat(ChatRequest(message="hello")):
        events.append(event)

    assert [event.type for event in events] == [
        "thought",
        "tool_call",
        "thought",
        "tool_result",
        "thought",
        "assistant_message",
        "done",
    ]
    assert events[0].content == "Planning next action with list_directory_tool."
    assert events[2].content == "Reviewing result from list_directory_tool."
    assert events[4].content == "Composing the response."


@pytest.mark.asyncio
async def test_completed_turn_count_includes_non_user_session_events(tmp_path: Path) -> None:
    settings = Settings(
        JARVIS_MEMORY_ROOT=str(tmp_path / "memory"),
        JARVIS_SQLITE_PATH=str(tmp_path / "jarvis.sqlite"),
    )
    runtime = AgentStreamRunner(
        settings,
        PathPolicy([tmp_path], full_access=True),
        McpService(),
        SessionTerminalService(),
        DesktopVisionService(settings),
        MemoryService(settings),
        ConversationContextService(settings.sqlite_path),
    )

    class _Event:
        def __init__(self, author: str, invocation_id: str) -> None:
            self.author = author
            self.invocation_id = invocation_id

    class _Session:
        def __init__(self) -> None:
            self.events = [
                _Event("user", "turn-1"),
                _Event("assistant", "turn-1"),
                _Event("assistant", "turn-2"),
                _Event("tool", "turn-3"),
                _Event("assistant", "turn-3"),
            ]

    class _SessionService:
        async def get_session(self, app_name: str, user_id: str, session_id: str):
            return _Session()

    runtime._session_service = _SessionService()

    assert await runtime._completed_turn_count("local-user", "session-1") == 3


async def test_build_runner_uses_workspace_and_browser_tools_only(
    monkeypatch, tmp_path: Path
) -> None:
    settings = Settings(
        JARVIS_MEMORY_ROOT=str(tmp_path / "memory"),
        JARVIS_SQLITE_PATH=str(tmp_path / "jarvis.sqlite"),
    )
    runtime = AgentStreamRunner(
        settings,
        PathPolicy([tmp_path], full_access=True),
        McpService(),
        SessionTerminalService(),
        DesktopVisionService(settings),
        MemoryService(settings),
        ConversationContextService(settings.sqlite_path),
    )

    workspace_tools = ["workspace:list_directory", "workspace:replace_file_section"]
    vision_tools = ["vision:capture_desktop_screenshot"]
    mcp_selection = SimpleNamespace(
        tools=["browser_navigate", "browser_snapshot"],
        total_resolved=2,
        playwright_resolved=2,
        playwright_selected=2,
        playwright_bundle="read",
        browser_intent=True,
        composite_tool_enabled=False,
    )
    captured: dict[str, object] = {}

    monkeypatch.setattr("app.agent.runner.build_workspace_tools", lambda policy: workspace_tools)
    monkeypatch.setattr(
        "app.agent.runner.build_vision_tools",
        lambda desktop_vision_service, policy: vision_tools,
    )

    async def _fake_select_mcp_tools(*args, **kwargs):
        return mcp_selection

    monkeypatch.setattr("app.agent.runner.select_mcp_tools", _fake_select_mcp_tools)
    monkeypatch.setattr(AgentStreamRunner, "_ensure_session_service", lambda self: object())
    monkeypatch.setattr(
        runtime.conversation_context_service,
        "render_session_context",
        lambda session_id: "",
    )

    def _fake_build_agent(
        settings, tools, skills_root, conversation_context, provider_config
    ) -> object:
        captured["tools"] = tools
        return object()

    monkeypatch.setattr("app.agent.runner.build_agent", _fake_build_agent)

    google_module = ModuleType("google")
    adk_module = ModuleType("google.adk")
    apps_module = ModuleType("google.adk.apps")
    app_module = ModuleType("google.adk.apps.app")
    runners_module = ModuleType("google.adk.runners")
    agents_module = ModuleType("google.adk.agents")
    context_cache_module = ModuleType("google.adk.agents.context_cache_config")

    class _FakeApp:
        def __init__(self, **kwargs) -> None:
            self.kwargs = kwargs

    class _FakeEventsCompactionConfig:
        def __init__(self, **kwargs) -> None:
            self.kwargs = kwargs

    class _FakeRunner:
        def __init__(self, app: object, session_service: object) -> None:
            self.app = app
            self.session_service = session_service

    class _FakeContextCacheConfig:
        def __init__(self, **kwargs) -> None:
            self.kwargs = kwargs

    app_module.App = _FakeApp
    app_module.EventsCompactionConfig = _FakeEventsCompactionConfig
    runners_module.Runner = _FakeRunner
    context_cache_module.ContextCacheConfig = _FakeContextCacheConfig

    google_module.adk = adk_module
    adk_module.apps = apps_module
    adk_module.runners = runners_module
    adk_module.agents = agents_module
    apps_module.app = app_module
    agents_module.context_cache_config = context_cache_module

    monkeypatch.setitem(sys.modules, "google", google_module)
    monkeypatch.setitem(sys.modules, "google.adk", adk_module)
    monkeypatch.setitem(sys.modules, "google.adk.apps", apps_module)
    monkeypatch.setitem(sys.modules, "google.adk.apps.app", app_module)
    monkeypatch.setitem(sys.modules, "google.adk.runners", runners_module)
    monkeypatch.setitem(sys.modules, "google.adk.agents", agents_module)
    monkeypatch.setitem(
        sys.modules,
        "google.adk.agents.context_cache_config",
        context_cache_module,
    )

    await runtime._build_runner(ChatRequest(message="inspect example.com", screen_share_enabled=True))

    assert captured["tools"] == [
        "workspace:list_directory",
        "workspace:replace_file_section",
        "vision:capture_desktop_screenshot",
        "browser_navigate",
        "browser_snapshot",
    ]


def test_speech_to_text_service_posts_multipart_audio(monkeypatch) -> None:
    settings = Settings(
        OPENROUTER_API_KEY="test-key",
        OPENROUTER_TRANSCRIPTION_MODEL="nvidia/parakeet-tdt-0.6b-v3",
    )
    service = SpeechToTextService(settings)
    seen: dict[str, object] = {}

    class _FakeResponse:
        status_code = 200
        text = "{\"text\": \"microphone transcript\"}"

        def json(self):
            return {"text": "microphone transcript"}

        def raise_for_status(self):
            return None

    class _FakeClient:
        def __init__(self, *args, **kwargs):
            seen["client_args"] = args
            seen["client_kwargs"] = kwargs
            seen["timeout"] = kwargs.get("timeout")

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def close(self):
            return None

        def post(self, url, files, data, headers):
            seen["url"] = url
            seen["files"] = files
            seen["data"] = data
            seen["headers"] = headers
            return _FakeResponse()

        def get(self, *args, **kwargs):
            return _FakeResponse()

        def request(self, *args, **kwargs):
            return _FakeResponse()

    import httpx

    monkeypatch.setattr(httpx, "Client", _FakeClient)

    result = service.transcribe_audio(b"audio-bytes", "speech.webm", "audio/webm")

    assert result["status"] == "success"
    assert result["data"]["text"] == "microphone transcript"
    assert seen["url"] == "https://openrouter.ai/api/v1/audio/transcriptions"
    assert seen["data"]["model"] == "nvidia/parakeet-tdt-0.6b-v3"
    assert seen["files"]["file"][2] == "audio/webm"
    assert seen["files"]["file"][0].endswith(".webm")
    assert seen["timeout"] == 60

def test_chat_runtime_translates_mcp_iserror_responses() -> None:
    runtime = object.__new__(AgentStreamRunner)

    class _Response:
        def __init__(self) -> None:
            self.name = "browser_navigate"
            self.response = {
                "content": [
                    {
                        "type": "text",
                        "text": "### Error\nError: Browser is already in use for cached profile",
                    }
                ],
                "isError": True,
            }

    class _Event:
        content = None

        def get_function_calls(self):
            return []

        def get_function_responses(self):
            return [_Response()]

    events = runtime._translate_event(_Event())

    assert len(events) == 1
    assert events[0].type == "tool_result"
    assert events[0].payload is not None
    assert events[0].payload.status == "error"
    assert "Browser is already in use" in (events[0].payload.detail or "")
