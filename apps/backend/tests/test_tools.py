from pathlib import Path
import json
import subprocess

from app.config import Settings
from app.mcp.adk_toolset import build_running_mcp_toolsets, resolve_running_mcp_tools
from app.schemas import McpActionRequest, McpToolConfig
from app.security.command_policy import CommandPolicy
from app.security.path_policy import PathPolicy
from app.runtime.adk_runner import ChatRuntime
from app.services.desktop_vision_service import DesktopVisionService
from app.services.memory_service import MemoryService
from app.services.mcp_service import McpService
from app.services.session_terminal_service import SessionTerminalService
from app.services.transcription_service import SpeechToTextService
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
    assert status["data"]["dreamer_model"] == "google/gemini-3.1-flash-lite"


def test_speech_to_text_service_posts_multipart_audio(monkeypatch) -> None:
    settings = Settings(
        OPENROUTER_API_KEY="test-key",
        OPENROUTER_TRANSCRIPTION_MODEL="nvidia/parakeet-tdt-0.6b-v3",
    )
    service = SpeechToTextService(settings)
    seen: dict[str, object] = {}

    class _FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self):
            return json.dumps(
                {
                    "text": "microphone transcript",
                    "model": "nvidia/parakeet-tdt-0.6b-v3",
                }
            ).encode("utf-8")

    def _fake_urlopen(request, timeout):
        seen["url"] = request.full_url
        seen["headers"] = dict(request.headers)
        seen["body"] = request.data
        seen["timeout"] = timeout
        return _FakeResponse()

    monkeypatch.setattr("app.services.transcription_service.urllib.request.urlopen", _fake_urlopen)

    result = service.transcribe_audio(b"audio-bytes", "speech.webm", "audio/webm")

    assert result["status"] == "success"
    assert result["data"]["text"] == "microphone transcript"
    assert seen["url"] == "https://openrouter.ai/api/v1/audio/transcriptions"
    headers = {key.lower(): value for key, value in seen["headers"].items()}
    assert "application/json" in str(headers.get("content-type"))
    payload = json.loads(seen["body"].decode("utf-8"))
    assert payload["model"] == "nvidia/parakeet-tdt-0.6b-v3"
    assert payload["input_audio"]["format"] == "webm"
    assert seen["timeout"] == 60

def test_chat_runtime_translates_mcp_iserror_responses() -> None:
    runtime = object.__new__(ChatRuntime)

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
