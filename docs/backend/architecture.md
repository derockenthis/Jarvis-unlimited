# Backend Architecture

## Purpose

The backend is the local FastAPI boundary for Jarvis Agent Desktop. It exposes HTTP APIs to the Electron renderer, builds the Google ADK agent runtime, gates filesystem and browser-facing tools, manages MCP tool availability, and stores ADK session, conversation history, and NBAM memory data locally.

The backend is intentionally split into thin route modules, service modules, runtime orchestration, tool wrappers, and safety policies. Route handlers should validate and hand off; most behavior belongs in services or runtime classes.

## Top-Level Layout

| Path | Responsibility |
| --- | --- |
| `app/main.py` | Creates the FastAPI app, configures CORS for the local renderer, and registers routers. |
| `app/config.py` | Loads environment and `.env` settings for models, storage paths, screenshots, and filesystem access. |
| `app/dependencies.py` | Provides cached service, runtime, policy, and settings dependencies. |
| `app/schemas.py` | Defines the HTTP and stream contracts shared by routes, services, and the renderer. |
| `app/routes/` | FastAPI route modules for health, chat, speech, MCP, and workspace APIs. |
| `app/services/` | Endpoint-facing business services: chat, MCP, memory, speech, desktop vision, terminal sessions, workspace roots, and conversation persistence. |
| `app/runtime/adk_runner.py` | Compatibility import surface for the canonical live chat runner. |
| `app/agent/agent.py` | Canonical ADK agent factory plus default ADK loader hook for local smoke tests and eval wiring. |
| `app/agent/prompt.py` | Owns the root instruction text and skills-folder context assembly. |
| `app/agent/provider_config.py` | Encapsulates request-scoped provider validation, model resolution, and provider environment setup. |
| `app/agent/event_translation.py` | Translates ADK events into the frontend stream contract and cleans assistant text. |
| `app/agent/runner.py` | Canonical live chat runtime adapter that builds per-request runners and streams translated events. |
| `app/agent/sub_agent_launcher.py` | CLI entrypoint for spawning isolated ADK sub-agents from the main orchestrator. |
| `app/agent/tools/` | ADK-facing tool composition layer grouped by workspace, terminal, memory, and vision domains. |
| `app/tools/` | Policy-bound file, search, edit, terminal, vision, memory, and ADK wrapper tools. |
| `app/security/` | Path and command policies used before local resources are touched. |
| `app/mcp/` | Built-in MCP presets and ADK `McpToolset` bridge. |
| `app/memory/` | NBAM storage primitives, schemas, validator, manifest, scout, and dreamer scaffold. |

## Request Flow

1. The renderer calls a local endpoint on `http://127.0.0.1:8765`.
2. `app/main.py` routes the request to one of the modules in `app/routes/`.
3. The route obtains cached dependencies from `app/dependencies.py`.
4. Service classes perform endpoint-specific orchestration or delegate to `ChatRuntime`.
5. Chat requests build an ADK `Runner` through `app/agent/runner.py`, attach only the tools allowed for that request, and translate ADK events into the renderer SSE contract.

## Route Layer

| Route | Module | Behavior |
| --- | --- | --- |
| `GET /health` | `routes/health.py` | Returns app health, OpenRouter configuration status, and ripgrep availability. |
| `POST /api/chat` | `routes/chat.py` | Streams `ChatEvent` objects as server-sent events. |
| `GET /api/conversations` | `routes/chat.py` | Returns recent persisted conversations for the current user. |
| `GET /api/conversations/{conversation_id}` | `routes/chat.py` | Returns one persisted conversation or `404`. |
| `GET /api/conversations/{conversation_id}/messages` | `routes/chat.py` | Returns persisted message rows for a conversation. |
| `GET /api/models/ollama` | `routes/chat.py` | Probes an Ollama server's `/api/tags` endpoint and returns model names. |
| `POST /api/speech/transcribe` | `routes/transcription.py` | Accepts recorded audio and returns transcribed text. |
| `GET /api/mcp/tools` | `routes/mcp.py` | Lists configured MCP tools and their current status. |
| `POST /api/mcp/tools/{tool_id}/start` | `routes/mcp.py` | Marks an MCP config running for future ADK chat runs. |
| `POST /api/mcp/tools/{tool_id}/stop` | `routes/mcp.py` | Marks an MCP config stopped for future ADK chat runs. |
| `GET /api/workspaces` | `routes/workspaces.py` | Returns full filesystem or configured workspace roots. |

Routes should stay thin. If a route grows state, subprocess handling, storage behavior, or tool logic, that code should move into `app/services/`, `app/runtime/`, or `app/tools/`.

## Dependency Graph

`app/dependencies.py` owns process-local singletons with `lru_cache`:

1. `Settings` from `get_settings()`.
2. `PathPolicy`, built from `Settings.allowed_root_paths` and `Settings.full_filesystem_access`.
3. `McpService`, `SessionTerminalService`, `DesktopVisionService`, and `MemoryService`.
4. `ChatRuntime`, which receives all long-lived services plus settings and path policy.
5. `ChatService`, a thin wrapper over `ChatRuntime` plus SQLite-backed conversation access.
6. `SpeechToTextService`, which uses local mlx-whisper or OpenRouter for transcription.

This keeps route handlers simple and lets tests override dependencies without importing ADK eagerly.

## Chat Runtime

`ChatRuntime` in `app/runtime/adk_runner.py` is now a compatibility shim over `AgentStreamRunner` in `app/agent/runner.py`, which is the backend's real orchestration class.

It does the following for each chat request:

1. Lazily creates a `SqliteSessionService` at `Settings.sqlite_path`.
2. Resolves running MCP tools through `McpService`.
3. Builds local filesystem/search/edit tools through `build_agent_tools(PathPolicy)`.
4. Resolves a request-scoped Playwright MCP subset through `select_mcp_tools(...)`, including the compact browser composite when browser intent is detected.
5. Adds desktop screenshot and image analysis tools only when `screen_share_enabled` is true.
6. Builds the root ADK agent from `app/agent/agent.py` using a request-scoped `ProviderRuntimeConfig` plus skills-folder context from `ChatRequest`.
7. Ensures an ADK session exists, then calls `Runner.run_async(...)`.
8. Translates ADK function calls, function responses, thought parts, and text parts into renderer events through `app/agent/event_translation.py`.
9. Appends user and assistant observations to NBAM through `MemoryService`.
10. Persists the incoming user prompt into `conversation_messages` before the ADK run starts when a `conversation_store` is attached.
11. Persists the final assistant response into `conversation_messages` after a successful run completes.
12. After a completed turn, checks how many new ADK session event rows were added in SQLite since the last successful promotion for that session.
13. When the configured memory promotion interval is reached, runs a deterministic promotion pass over unconsolidated observations for that session.

The runtime also detects stale ADK session failures caused by missing tool results or removed tools. On those known recoverable errors it deletes and recreates the ADK session once, then retries the current request.

## Sub-Agent Launcher

`app/agent/tools/cli.py` exposes a `spawn_sub_agent` tool that shells out to `python -m app.agent.sub_agent_launcher` with a JSON spec file.

The launcher in `app/agent/sub_agent_launcher.py` builds a nested ADK agent from the provided spec:

1. It uses the request-scoped filesystem policy from the parent runtime.
2. It resolves only the tool groups requested in the spec.
3. It defaults sub-agents to `google/gemma-4-26b-a4b-it` through OpenRouter.
4. It runs each sub-agent in its own temporary SQLite session database.
5. It uses a separate Playwright preset for sub-agents so browser sessions do not reuse the main agent's shared Chromium context.

This keeps the orchestrator lightweight while still letting it delegate narrow tasks to isolated local subprocesses.

## Stream Contract

The backend streams JSON objects shaped by `ChatEvent`:

| Event type | Source | Frontend meaning |
| --- | --- | --- |
| `thought` | ADK `Part.thought` text or runtime recovery notice | Temporary reasoning/activity row. |
| `tool_call` | ADK function call | Tool activity row with `tool_name`, `status`, and optional JSON args. |
| `tool_result` | ADK function response | Tool completion row with status and detail, error, diff, or data summary. |
| `assistant_message` | Normal ADK text part | Appended into the active assistant message. |
| `error` | Runtime or service failure | Rendered as an error message. |
| `done` | End of backend stream | Clears transient frontend activity and closes the assistant turn. |

`app/agent/event_translation.py` strips provider channel markers from final assistant text before the renderer sees it.

## Conversation Persistence

Conversation persistence is currently owned by `ChatService`.

It initializes two SQLite tables under `Settings.sqlite_path`:

1. `conversations`: `id`, `user_id`, `title`, `created_at`, `updated_at`.
2. `conversation_messages`: `id`, `conversation_id`, `role`, `content`, `created_at`.

The current flow is:

1. The renderer sends `session_id` on every `/api/chat` request.
2. `AgentStreamRunner.stream_chat(...)` derives a conversation title from the first user message line and calls `ChatService.save_conversation(...)`.
3. The same request saves the raw user prompt as a `conversation_messages` row before the ADK run.
4. When the ADK stream finishes successfully, the backend saves the final assistant text as another `conversation_messages` row.
5. The renderer later loads recent titles through `/api/conversations` and hydrates old chats through `/api/conversations/{conversation_id}/messages`.

## Model Providers

The default environment path still centers on OpenRouter:

1. `Settings.openrouter_model` becomes a LiteLLM `openrouter/...` model string.
2. `Settings.openrouter_api_key` and `Settings.openrouter_base_url` populate OpenRouter/OpenAI-compatible environment variables.
3. Vision and speech services separately use OpenRouter-specific settings.

The current request schema and renderer now carry provider settings:

1. `provider`: `openrouter`, `openai`, `ollama`, or another model prefix.
2. `model`: provider-specific model name.
3. `api_key`: user-entered key from the sidebar.
4. `base_url`: optional provider base URL, also used for Ollama discovery.
5. `speech_model`: optional speech-to-text model (local mlx-whisper or OpenRouter), configurable per provider and persisted in SQLite.

`ProviderRuntimeConfig` maps these into LiteLLM model strings:

1. OpenRouter: `openrouter/{model}` unless already prefixed.
2. OpenAI: `openai/{model}` unless already prefixed.
3. Ollama: `ollama_chat/{model}` unless already prefixed.

`ChatRuntime.stream_chat(...)` validates provider configuration before building the runner. OpenRouter uses either the request API key or `OPENROUTER_API_KEY`, OpenAI requires a request API key from the sidebar, and Ollama does not require an API key. Ollama requests currently run without ADK tool declarations because local models can answer normally through LiteLLM while producing malformed partial JSON when forced through function-calling mode.

## Tools And Safety

All custom ADK tools are built from testable functions that receive a `PathPolicy`, then exposed to the agent through `app/agent/tools/` and the lower-level wrappers in `app/tools/agent_tools.py`.

| Tool area | Files | Safety boundary |
| --- | --- | --- |
| File listing/tree | `tools/file_explorer.py` | Resolves paths through `PathPolicy`, skips noisy folders such as `.git`, `node_modules`, `__pycache__`, and `.venv`. |
| File reads/search | `tools/search_tools.py` | Limits file size, rejects binary content, uses `rg` with no shell, timeout, and max result cap. |
| File edits | `tools/edit_tools.py` | Resolves paths first and returns unified diffs for creates, replacements, and insertions. |
| Terminal sessions | `tools/terminal_tools.py`, `services/session_terminal_service.py` | Requires a spawned session, validates commands with `CommandPolicy`, rejects shell control syntax, caps output, and enforces cwd path policy. |
| Vision | `tools/vision_tools.py`, `services/desktop_vision_service.py` | Registered only for screen-sharing requests; screenshots are saved under the configured screenshot directory. |
| Memory | `tools/memory_tools.py`, `services/memory_service.py` | Allows status inspection and node reads, not arbitrary durable graph mutation. |

`PathPolicy` supports either full filesystem access or scoped access to granted roots. In scoped mode it rejects path traversal and symlink escapes by resolving the target before checking ancestor paths.

`CommandPolicy` only allows a small command set and read-only git subcommands. It rejects shell control characters, executable paths, redirection, pipes, substitutions, and unapproved executables.

`CLIAgentTool` is the only wrapper that may spawn sub-agents. It validates the tool allowlist, writes a temporary JSON spec, and launches the launcher with the current backend's Python interpreter so the sub-agent inherits the same virtual environment and import paths.

## MCP

The first built-in MCP preset is Playwright. It is defined in `app/mcp/presets.py` and starts as enabled, auto-started, and running. The main agent uses the shared-browser preset, while sub-agents request the isolated preset so they do not steal each other's Chromium context.

`McpService` keeps the in-memory registry, remembers manually stopped tools so auto-start does not immediately re-enable them, caches ADK toolsets by command fingerprint, and closes stale toolsets when configs stop running.

Running configs are bridged into ADK with `build_mcp_toolset(...)`, which uses `StdioConnectionParams` and a 60-second timeout to tolerate slow first browser launches.

MCP state is not yet durable. Restarting the backend rebuilds the preset state from code.

## Memory

NBAM storage is separate from ADK sessions.

1. ADK sessions live in SQLite through `SqliteSessionService` and track chat/runtime state.
2. Conversation metadata and message history live in the `conversations` and `conversation_messages` SQLite tables managed by `ChatService`.
3. NBAM observations live in the `observations` SQLite table managed by `ObservationLog`.
4. Durable memory nodes are markdown files under `Settings.memory_root / nodes` managed by `NodeStore`.
5. `MemoryService` initializes storage, appends observations, tracks the last promoted event-count cursor per session, promotes validated `create_node` patches from unconsolidated observations, reports status, and reads nodes.

The memory package includes schema, manifest, scout, dreamer, and validator modules. Live chat now uses an ADK-backed dreamer proposer with a deterministic fallback stub plus validation to promote observations into durable node files. The promotion trigger is based on new rows in the ADK `events` table since the last promotion, not on coarse compaction-cycle buckets. When a promoted node has no parent, the backend automatically creates a stable tree-root node such as `general-root` or `project-scope-root` before writing the child node.

After compaction thresholds are reached, `AgentStreamRunner` prunes old SQLite rows from the `events` table for the active `app_name`, `user_id`, and `session_id`, while retaining the most recent overlap window. It also updates the memory promotion cursor so the next promotion pass stays aligned with the retained event history. The richer scout and multi-op patch pipeline remain future work.

## Validation

Backend tests cover health, API stream formatting by dependency override, MCP preset behavior, path policy behavior, custom tools, and NBAM primitives. Use:

```bash
cd apps/backend
uv run pytest
```

In this local setup, `uv` may be installed under `~/Library/Python/3.14/bin/uv`; ensure that directory is on `PATH` when running root scripts.
