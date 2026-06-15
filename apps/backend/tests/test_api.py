from fastapi.testclient import TestClient

from app.agent.runner import AgentStreamRunner
from app.dependencies import get_chat_service
from app.dependencies import get_settings_service
from app.dependencies import get_speech_to_text_service
from app.main import app
from app.config import Settings
from app.schemas import ChatEvent, ChatEventPayload, ChatRequest
from app.security.path_policy import PathPolicy
from app.services.desktop_vision_service import DesktopVisionService
from app.services.conversation_context_service import ConversationContextService
from app.services.memory_service import MemoryService
from app.services.mcp_service import McpService
from app.services.session_terminal_service import SessionTerminalService
from app.services.settings_service import SettingsService


def test_health_endpoint() -> None:
    client = TestClient(app)

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_mcp_tools_includes_playwright_preset() -> None:
    client = TestClient(app)

    response = client.get("/api/mcp/tools")

    assert response.status_code == 200
    tools = response.json()["tools"]
    assert tools[0]["id"] == "playwright"
    assert tools[0]["command"] == "npx"


class _StubChatService:
    async def stream_chat(self, request: ChatRequest):
        yield ChatEvent(type="thought", content="Planning the response.")
        yield ChatEvent(
            type="tool_call",
            content="Calling list_directory_tool",
            payload=ChatEventPayload(tool_name="list_directory_tool", status="running"),
        )
        yield ChatEvent(
            type="tool_result",
            content="list_directory_tool finished",
            payload=ChatEventPayload(tool_name="list_directory_tool", status="success"),
        )
        yield ChatEvent(type="assistant_message", content=f"Echo: {request.message}")
        yield ChatEvent(type="done", content="Chat stream completed.")


def test_chat_stream_returns_agent_activity_events() -> None:
    app.dependency_overrides[get_chat_service] = lambda: _StubChatService()
    try:
        client = TestClient(app)

        with client.stream("POST", "/api/chat", json={"message": "hello"}) as response:
            body = "".join(response.iter_text())
    finally:
        app.dependency_overrides.pop(get_chat_service, None)

    assert response.status_code == 200
    assert '"type": "thought"' in body
    assert '"type": "tool_call"' in body
    assert '"type": "tool_result"' in body
    assert '"type": "assistant_message"' in body
    assert '"type": "done"' in body


def test_chat_runtime_allows_ollama_without_openrouter_key(tmp_path) -> None:
    settings = Settings(
        OPENROUTER_API_KEY="",
        JARVIS_SQLITE_PATH=tmp_path / "jarvis.sqlite",
        JARVIS_MEMORY_ROOT=tmp_path / "memory",
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
    request = ChatRequest(message="hello", provider="ollama", model="gemma4:12b")

    assert runtime._missing_provider_configuration(request) is None
    assert runtime._provider_supports_adk_tools(request.provider) is True


def test_mcp_start_and_stop_updates_status() -> None:
    client = TestClient(app)

    start_response = client.post("/api/mcp/tools/playwright/start", json={})
    stop_response = client.post("/api/mcp/tools/playwright/stop", json={})

    assert start_response.status_code == 200
    assert start_response.json()["status"] == "running"
    assert stop_response.status_code == 200
    assert stop_response.json()["status"] == "stopped"


def test_model_settings_round_trip(tmp_path) -> None:
    service = SettingsService(
        Settings(
            JARVIS_SQLITE_PATH=tmp_path / "jarvis.sqlite",
            JARVIS_MEMORY_ROOT=tmp_path / "memory",
        )
    )
    app.dependency_overrides[get_settings_service] = lambda: service
    try:
        client = TestClient(app)

        save_response = client.put(
            "/api/settings/model",
            json={
                "provider": "ollama",
                "model": "gemma4:12b",
                "api_key": "",
                "base_url": "http://localhost:11434",
            },
        )
        get_response = client.get("/api/settings/model")
    finally:
        app.dependency_overrides.pop(get_settings_service, None)

    assert save_response.status_code == 200
    assert save_response.json()["current_provider"] == "ollama"
    assert get_response.status_code == 200
    assert get_response.json()["current_provider"] == "ollama"
    assert get_response.json()["providers"] == [
        {
            "provider": "ollama",
            "model": "gemma4:12b",
            "api_key": "",
            "base_url": "http://localhost:11434",
        }
    ]


class _StubSpeechToTextService:
    def transcribe_audio(self, audio_bytes: bytes, filename: str, content_type: str | None):
        return {
            "status": "success",
            "data": {
                "text": "hello from the microphone",
                "model": "nvidia/parakeet-tdt-0.6b-v3",
            },
        }


def test_speech_transcription_route_returns_text() -> None:
    app.dependency_overrides[get_speech_to_text_service] = lambda: _StubSpeechToTextService()
    try:
        client = TestClient(app)

        response = client.post(
            "/api/speech/transcribe",
            files={"audio": ("speech.webm", b"audio-bytes", "audio/webm")},
        )
    finally:
        app.dependency_overrides.pop(get_speech_to_text_service, None)

    assert response.status_code == 200
    assert response.json()["text"] == "hello from the microphone"
    assert response.json()["model"] == "nvidia/parakeet-tdt-0.6b-v3"
