# Backend API Services

## Scope

This document covers route handlers, dependency wiring, and endpoint-facing services that are not themselves the ADK runtime.

Primary files:

| File | Role |
| --- | --- |
| `apps/backend/app/main.py` | FastAPI app, CORS, and router registration. |
| `apps/backend/app/dependencies.py` | Cached dependency providers. |
| `apps/backend/app/routes/health.py` | Health endpoint. |
| `apps/backend/app/routes/chat.py` | Chat stream endpoint and Ollama model discovery endpoint. |
| `apps/backend/app/routes/transcription.py` | Speech transcription endpoint. |
| `apps/backend/app/routes/mcp.py` | MCP tool list/start/stop endpoints. |
| `apps/backend/app/routes/workspaces.py` | Workspace root endpoint. |
| `apps/backend/app/services/health_service.py` | Health response construction. |
| `apps/backend/app/services/chat_service.py` | Thin chat service facade. |
| `apps/backend/app/services/transcription_service.py` | OpenRouter speech-to-text integration. |
| `apps/backend/app/services/workspace_service.py` | Workspace root projection. |

## App Initialization

`app/main.py` creates `FastAPI(title="Jarvis Agent Backend", version="0.1.0")`, adds CORS for the local Vite renderer origins, and includes routers in this order:

1. Health.
2. Chat.
3. Speech transcription.
4. MCP.
5. Workspaces.

CORS allows `http://127.0.0.1:5173` and `http://localhost:5173`, with all methods and headers. This is tailored to the local Vite/Electron development renderer.

## Dependency Providers

`app/dependencies.py` uses `lru_cache(maxsize=1)` to provide process-local singletons:

| Provider | Returns | Notes |
| --- | --- | --- |
| `get_path_policy()` | `PathPolicy` | Built from current settings. |
| `get_chat_runtime()` | `ChatRuntime` | Receives settings, path policy, MCP, terminal, vision, and memory services. |
| `get_chat_service()` | `ChatService` | Thin wrapper over `ChatRuntime`. |
| `get_mcp_service()` | `McpService` | In-memory MCP registry. |
| `get_session_terminal_service()` | `SessionTerminalService` | In-memory guarded terminal sessions. |
| `get_desktop_vision_service()` | `DesktopVisionService` | Screenshot and image analysis service. |
| `get_memory_service()` | `MemoryService` | NBAM observation and node storage. |
| `get_speech_to_text_service()` | `SpeechToTextService` | OpenRouter speech service. |
| `settings_dependency()` | `Settings` | Route-friendly settings dependency. |

This structure keeps ADK and subprocess-heavy objects out of route files and makes tests easier to override.

## Health Service

The health route returns `HealthResponse` from `services/health_service.py`.

It reports:

1. Backend status and app name.
2. Whether OpenRouter is configured.
3. Whether `rg` is available for search tools.

The frontend and setup scripts use this endpoint to confirm the backend is reachable.

## Chat Service

`ChatService` is intentionally small:

1. It receives `ChatRuntime` in its constructor.
2. Its `stream_chat(...)` method delegates to `runtime.stream_chat(...)`.

This gives routes a service abstraction while keeping all runtime complexity in one class.

## Ollama Model Discovery

`GET /api/models/ollama` lives in `routes/chat.py` because the model picker was added near chat provider handling. It accepts an optional `base_url`, defaults to `http://localhost:11434`, then calls:

```text
{base_url}/api/tags
```

It returns:

```json
{ "models": ["model-name"] }
```

On connection or parsing errors, it returns a JSON payload with an empty model list and an `error` string. The renderer treats an empty list as no detected models.

Current revision opportunity: this endpoint could move into a dedicated `routes/models.py` and `services/model_service.py` if provider handling grows beyond Ollama discovery.

## Speech-To-Text Service

`routes/transcription.py` accepts a multipart upload named `audio`. It reads the bytes, forwards them to `SpeechToTextService.transcribe_audio(...)`, then returns `SpeechTranscriptionResponse` on success.

`SpeechToTextService`:

1. Requires a local `ffmpeg` binary so recorded `webm` or `ogg` audio can be decoded.
2. Requires the `mlx-whisper` Python package in the backend environment.
3. Writes the uploaded audio to a temporary local file with a suffix derived from filename or MIME type.
4. Calls `mlx_whisper.transcribe(...)` with the configured local Whisper model id.
5. Returns text and model name, or a structured error.

Missing dependency failures are converted into useful user-facing install messages.

## Workspace Service

`get_workspace_roots(settings)` returns either:

1. `/` with access `full` when `JARVIS_FULL_FILESYSTEM_ACCESS=true`.
2. Configured allowed roots with access `granted` otherwise.

This endpoint is informational for the UI and helps expose what the backend will allow through `PathPolicy`.

## MCP Route Service Boundary

MCP routes are thin facades over `McpService`:

1. Listing serializes the current `McpToolConfig` values.
2. Start/stop accepts `McpActionRequest` and returns `McpActionResponse`.

The route does not launch browser automation directly. It marks configs as running or stopped. `ChatRuntime` later resolves running configs into ADK MCP tools when building an agent.

## Error Style

Most services return structured dictionaries or Pydantic response models rather than raising raw exceptions. Routes convert known service failures into HTTP errors when needed, such as speech transcription returning `503` for missing configuration and `502` for upstream transcription failures.

## Revision Notes

1. Consider moving model discovery out of `routes/chat.py` if more providers are added.
2. API keys sent from the renderer should eventually be handled by secure storage or a backend settings service rather than plain localStorage and request payloads.
3. Health currently reports OpenRouter configuration only; provider-aware health could report OpenAI and Ollama readiness too.