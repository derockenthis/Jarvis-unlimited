# Backend API Services

## Scope

This document covers route handlers, dependency wiring, and endpoint-facing services that are not themselves the ADK runtime.

Primary files:

| File | Role |
| --- | --- |
| `apps/backend/app/main.py` | FastAPI app, CORS, and router registration. |
| `apps/backend/app/dependencies.py` | Cached dependency providers. |
| `apps/backend/app/routes/health.py` | Health endpoint. |
| `apps/backend/app/routes/chat.py` | Chat stream, conversation history, and Ollama model discovery endpoints. |
| `apps/backend/app/routes/transcription.py` | Speech transcription endpoint. |
| `apps/backend/app/routes/mcp.py` | MCP tool list/start/stop endpoints. |
| `apps/backend/app/routes/workspaces.py` | Workspace root endpoint. |
| `apps/backend/app/services/health_service.py` | Health response construction. |
| `apps/backend/app/services/chat_service.py` | Thin chat service facade. |
| `apps/backend/app/services/transcription_service.py` | Local mlx-whisper speech-to-text integration. |
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
| `get_speech_to_text_service()` | `SpeechToTextService` | Local mlx-whisper speech service. |
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

`ChatService` is intentionally small, but it now owns conversation persistence:

1. It receives `ChatRuntime` plus `Settings` in its constructor.
2. It initializes SQLite tables for `conversations` and `conversation_messages`.
3. Its `stream_chat(...)` method delegates to `runtime.stream_chat(...)`.
4. It provides `save_conversation(...)`, `save_conversation_message(...)`, `list_conversations(...)`, `get_conversation(...)`, and `get_conversation_messages(...)`.

This gives routes a service abstraction while keeping ADK runtime complexity in one class.

Conversation routes currently exposed from `routes/chat.py`:

1. `GET /api/conversations`
2. `GET /api/conversations/{conversation_id}`
3. `GET /api/conversations/{conversation_id}/messages`

These routes back the renderer sidebar and chat-history hydration flow.

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

`routes/transcription.py` accepts a multipart upload named `audio` and an optional `model` form field. It reads the bytes, forwards them to `SpeechToTextService.transcribe_audio(...)`, then returns `SpeechTranscriptionResponse` on success.

`SpeechToTextService`:

1. Requires `mlx-whisper` to be installed (`pip install mlx-whisper`) for local transcription.
2. Writes the audio bytes to a temporary file.
3. Routes transcription based on the model prefix:
   - **Local (mlx-whisper)**: Models without `openrouter/` prefix. Default `mlx-community/whisper-large-v3-turbo`. Runs fully locally on Apple Silicon via MLX.
   - **OpenRouter**: Models prefixed with `openrouter/` (e.g., `openrouter/qwen/qwen3-asr-flash-2026-02-10`). Requires `OPENROUTER_API_KEY` and `httpx`.
4. Returns text and model name, or a structured error.

The first local transcription call downloads the Whisper model from HuggingFace (~1.5 GB), cached in `~/.cache/huggingface/`. Subsequent calls are fast and fully local. OpenRouter models require no local download but need network access and an API key.

The model can be configured per-provider in the UI (Provider Settings → Speech Model) and is persisted in SQLite alongside other provider settings.

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

1. Conversation message history currently stores only `role`, `content`, and timestamps; if historical tool activity or thoughts need to be reconstructed, the schema will need to expand.
2. Consider moving model discovery out of `routes/chat.py` if more providers are added.
3. API keys sent from the renderer should eventually be handled by secure storage or a backend settings service rather than plain local request payloads.
4. Health currently reports OpenRouter configuration only; provider-aware health could report OpenAI and Ollama readiness too.
